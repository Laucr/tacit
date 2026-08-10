#!/usr/bin/env python3
"""
honcho_manage.py — Administrative operations for Honcho memory sidecar.

Subcommands:
    setup                   First-time bootstrap (docker compose up, create workspace/peers)
    status                  Health check and stats
    session map <name>      Bind to a named Honcho session
    session list            List all sessions
    session show <name>     Show session details
    forget <id>             Delete a specific observation by ID
    forget --query <q>      Search and delete matching observations
    forget --session <name> Wipe all observations for a session
    config show             Show current connection config
    config set <key> <val>  Update connection config

Usage:
    python honcho_manage.py setup
    python honcho_manage.py status
    python honcho_manage.py session map my-project
    python honcho_manage.py forget abc123
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

_GLOBAL_DEFAULT = os.path.join(os.path.expanduser("~"), ".honcho")


def _honcho_dir() -> str:
    """Resolve config from HONCHO_HOME, cwd/repo, project-local, then global."""
    explicit = os.environ.get("HONCHO_HOME", "")
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    current = os.path.abspath(os.getcwd())
    if os.path.isfile(os.path.join(current, "docker-compose.yml")):
        return current
    for _ in range(10):
        candidate = os.path.join(current, ".claude", "honcho")
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return _GLOBAL_DEFAULT


def _load_dotenv():
    """Load .env from the directory used for session and Compose state."""
    env_file = os.path.join(_honcho_dir(), ".env")
    if os.path.isfile(env_file):
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k not in os.environ:
                    os.environ[k] = v


_load_dotenv()

HONCHO_BASE = os.environ.get("HONCHO_BASE_URL", "http://localhost:8787")
WORKSPACE = os.environ.get("HONCHO_WORKSPACE", "claude-code")
OBSERVER = os.environ.get("HONCHO_OBSERVER", "claude-code")
OBSERVED = os.environ.get("HONCHO_OBSERVED", "user")

def _session_file() -> str:
    return os.path.join(_honcho_dir(), "session.json")


def _list_all_sessions() -> list[dict]:
    """Fetch every sessions page instead of silently truncating at one page."""
    items: list[dict] = []
    page = 1
    while True:
        result = _api(
            "POST",
            f"/v3/workspaces/{WORKSPACE}/sessions/list?size=100&page={page}",
            {},
        )
        batch = result.get("items", []) if isinstance(result, dict) else []
        items.extend(batch)
        pages = result.get("pages", page) if isinstance(result, dict) else page
        if not batch or page >= pages:
            return items
        page += 1


def _api(method: str, path: str, body: dict | None = None) -> dict | list:
    url = f"{HONCHO_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        raise RuntimeError(f"HTTP {e.code}: {err_body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection error: {e.reason}") from e


def _health_check() -> bool:
    try:
        result = _api("GET", "/health")
        return isinstance(result, dict) and result.get("status") == "ok"
    except RuntimeError:
        return False


# ── setup ─────────────────────────────────────────────────────────────────

def _read_env_var(env_file: str, key: str) -> str | None:
    """Read a variable from a .env file (simple KEY=VALUE parsing)."""
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    k, _, v = line.partition("=")
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def _parse_pg_uri(uri: str) -> dict:
    """
    Parse a PostgreSQL URI into components.
    Handles: postgresql+psycopg://user:pass@host:port/dbname
    Returns dict with keys: user, password, host, port, dbname, base_uri (without dbname).
    """
    # Strip the scheme
    rest = uri
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if rest.startswith(prefix):
            rest = rest[len(prefix):]
            break

    # Split user:pass@host:port/dbname
    auth, _, hostpath = rest.rpartition("@")
    user, _, password = auth.partition(":") if auth else ("", "", "")
    hostport, _, dbname = hostpath.partition("/")
    host, _, port_str = hostport.partition(":")
    port = port_str or "5432"

    # Build a base URI pointing to the default 'postgres' database for admin operations
    scheme = "postgresql+psycopg://"
    if user and password:
        base_uri = f"{scheme}{user}:{password}@{host}:{port}/postgres"
    elif user:
        base_uri = f"{scheme}{user}@{host}:{port}/postgres"
    else:
        base_uri = f"{scheme}{host}:{port}/postgres"

    return {
        "user": user,
        "password": password,
        "host": host,
        "port": port,
        "dbname": dbname or "honcho",
        "base_uri": base_uri,
    }


def _provision_database(db_uri: str) -> None:
    """
    Ensure the target database exists before the Honcho container starts.

    Only creates the database if it doesn't exist. Schema setup (pgvector
    extension, tables, migrations) is handled by Honcho's own entrypoint
    via scripts/provision_db.py -> src.db.init_db().

    Uses psql if available, falls back to psycopg if importable,
    otherwise prints manual instructions.
    """
    parsed = _parse_pg_uri(db_uri)
    dbname = parsed["dbname"]
    host = parsed["host"]
    port = parsed["port"]
    user = parsed["user"]
    password = parsed["password"]

    print(f"Checking database '{dbname}' on {host}:{port}...")

    # Try psql first (most commonly available)
    psql_env = dict(os.environ)
    if password:
        psql_env["PGPASSWORD"] = password

    psql_base_args = ["psql", "-h", host, "-p", port]
    if user:
        psql_base_args.extend(["-U", user])

    psql_available = subprocess.run(
        ["which", "psql"], capture_output=True
    ).returncode == 0

    if psql_available:
        check = subprocess.run(
            [*psql_base_args, "-d", "postgres", "-tAc",
             f"SELECT 1 FROM pg_database WHERE datname = '{dbname}'"],
            capture_output=True, text=True, env=psql_env,
        )
        if check.returncode != 0:
            print(f"  Warning: Could not connect to PostgreSQL: {check.stderr.strip()}")
            print(f"  Make sure PostgreSQL is running and accessible at {host}:{port}")
            return

        if "1" not in (check.stdout or ""):
            print(f"  Creating database '{dbname}'...")
            create = subprocess.run(
                [*psql_base_args, "-d", "postgres", "-c",
                 f'CREATE DATABASE "{dbname}"'],
                capture_output=True, text=True, env=psql_env,
            )
            if create.returncode != 0:
                print(f"  Error creating database: {create.stderr.strip()}", file=sys.stderr)
                print(f"  Please create it manually: CREATE DATABASE \"{dbname}\";")
                return
            print(f"  Database '{dbname}' created.")
        else:
            print(f"  Database '{dbname}' already exists.")

        print("  (pgvector extension + tables will be set up by Honcho on first start)")
        return

    # Fallback: try psycopg directly (if installed in the environment)
    try:
        import psycopg  # type: ignore

        admin_dsn = f"host={host} port={port} dbname=postgres"
        if user:
            admin_dsn += f" user={user}"
        if password:
            admin_dsn += f" password={password}"

        with psycopg.connect(admin_dsn, autocommit=True) as conn, conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)
                )
                if not cur.fetchone():
                    print(f"  Creating database '{dbname}'...")
                    cur.execute(f'CREATE DATABASE "{dbname}"')
                    print(f"  Database '{dbname}' created.")
                else:
                    print(f"  Database '{dbname}' already exists.")

        print("  (pgvector extension + tables will be set up by Honcho on first start)")
        return
    except ImportError:
        pass
    except Exception as e:
        print(f"  Database check via psycopg failed: {e}", file=sys.stderr)

    # Last resort: print manual instructions
    print("\n  Could not auto-check database (psql and psycopg not available).")
    print("  Please ensure the database exists before starting Honcho:\n")
    print(f'    CREATE DATABASE "{dbname}";')
    print("\n  Honcho will handle pgvector + schema setup on first start.")


def cmd_setup(args: list[str]):
    """Bootstrap the Honcho sidecar."""
    honcho_dir = _honcho_dir()
    compose_file = os.path.join(honcho_dir, "docker-compose.yml")

    if not os.path.isfile(compose_file):
        print(f"Error: docker-compose.yml not found at {compose_file}", file=sys.stderr)
        print("Make sure you're in the project root.", file=sys.stderr)
        sys.exit(1)

    # Ensure the honcho config directory exists
    os.makedirs(honcho_dir, exist_ok=True)

    env_file = os.path.join(honcho_dir, ".env")
    if not os.path.isfile(env_file):
        example = os.path.join(honcho_dir, ".env.example")
        if os.path.isfile(example):
            shutil.copyfile(example, env_file)
            print(f"Created {env_file} from .env.example.")
        else:
            print(f"Error: neither {env_file} nor {example} exists.", file=sys.stderr)
            sys.exit(1)

    # Read DB URI from .env to provision database + pgvector before Docker starts
    db_uri = _read_env_var(env_file, "HONCHO_DB_URI")
    if db_uri:
        _provision_database(db_uri)
    else:
        print("Using the PostgreSQL service managed by Docker Compose.")

    # Start containers
    print("\nStarting Honcho sidecar...")
    result = subprocess.run(
        [
            "docker", "compose", "--project-directory", honcho_dir,
            "-f", compose_file, "up", "-d", "--build",
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Docker compose failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(result.stdout)

    # Wait for health
    print("Waiting for Honcho API to be ready...")
    import time
    for _attempt in range(300):
        if _health_check():
            print("Honcho API is healthy.")
            break
        time.sleep(2)
    else:
        print("Honcho API did not become healthy within 10 minutes.", file=sys.stderr)
        subprocess.run(
            ["docker", "compose", "--project-directory", honcho_dir, "-f", compose_file, "ps"],
            check=False,
        )
        sys.exit(1)

    # Create workspace (idempotent — returns existing if name matches)
    print(f"Ensuring workspace '{WORKSPACE}'...")
    try:
        _api("POST", "/v3/workspaces", {"name": WORKSPACE})
    except RuntimeError as e:
        if "409" not in str(e) and "200" not in str(e):
            print(f"Warning: workspace creation: {e}", file=sys.stderr)

    # Create peers (idempotent)
    print(f"Ensuring peers '{OBSERVER}' and '{OBSERVED}'...")
    try:
        _api("POST", f"/v3/workspaces/{WORKSPACE}/peers", {
            "name": OBSERVED,
        })
    except RuntimeError as e:
        if "409" not in str(e) and "200" not in str(e):
            print(f"Warning: peer creation ({OBSERVED}): {e}", file=sys.stderr)

    try:
        _api("POST", f"/v3/workspaces/{WORKSPACE}/peers", {
            "name": OBSERVER,
            "configuration": {"observe_me": False},
        })
    except RuntimeError as e:
        if "409" not in str(e) and "200" not in str(e):
            print(f"Warning: peer creation ({OBSERVER}): {e}", file=sys.stderr)

    # Initialize session.json if not exists
    sf = _session_file()
    if not os.path.isfile(sf):
        os.makedirs(os.path.dirname(sf), exist_ok=True)
        with open(sf, "w") as f:
            json.dump({"session": "global"}, f, indent=2)
        print(f"Created session config: {sf} (default: global)")

    # Create the default 'global' session (idempotent)
    print("Ensuring default 'global' session...")
    try:
        _api("POST", f"/v3/workspaces/{WORKSPACE}/sessions", {"name": "global"})
    except RuntimeError as e:
        if "409" not in str(e) and "200" not in str(e):
            print(f"Warning: session creation (global): {e}", file=sys.stderr)

    print("\nSetup complete. Memory is ready.")
    print("  - /honcho-remember  to save facts")
    print("  - /honcho-recall    to query memories")
    print("  - /honcho-manage session map <name>  to scope to a project")


# ── status ────────────────────────────────────────────────────────────────

def cmd_status(args: list[str]):
    """Show Honcho health and memory stats."""
    # Health check
    if _health_check():
        print("Honcho API: HEALTHY")
    else:
        print("Honcho API: NOT REACHABLE")
        print("Run /honcho-manage setup to start the sidecar.")
        return

    # Active session
    sf = _session_file()
    session = "global"
    if os.path.isfile(sf):
        try:
            with open(sf) as f:
                session = json.load(f).get("session", "global")
        except (json.JSONDecodeError, OSError):
            pass
    print(f"Active session: {session}")

    # Count conclusions
    try:
        result = _api("POST", f"/v3/workspaces/{WORKSPACE}/conclusions/list?size=1", {})
        total = result.get("total", 0) if isinstance(result, dict) else "?"
        print(f"Total observations: {total}")
    except RuntimeError:
        print("Total observations: (unable to query)")


# ── session ───────────────────────────────────────────────────────────────

def cmd_session(args: list[str]):
    """Manage session binding."""
    if not args:
        print("Usage: session map <name> | session list | session show <name>", file=sys.stderr)
        sys.exit(1)

    sub = args[0]

    if sub == "map":
        if len(args) < 2:
            print("Usage: session map <name>", file=sys.stderr)
            sys.exit(1)
        name = args[1]
        sf = _session_file()
        os.makedirs(os.path.dirname(sf), exist_ok=True)
        with open(sf, "w") as f:
            json.dump({"session": name}, f, indent=2)
        print(f"Active session set to: {name}")
        print("Subsequent /honcho-remember and /honcho-recall will use this session.")

    elif sub == "list":
        try:
            items = _list_all_sessions()
            if not items:
                print("No sessions found.")
                return
            print("Sessions:")
            for s in items:
                name = s.get("name", s.get("id", "?"))
                created = s.get("created_at", "")[:10]
                print(f"  - {name} (created: {created})")
        except RuntimeError as e:
            print(f"Error listing sessions: {e}", file=sys.stderr)

    elif sub == "show":
        if len(args) < 2:
            print("Usage: session show <name>", file=sys.stderr)
            sys.exit(1)
        name = args[1]
        sf = _session_file()
        current = "global"
        if os.path.isfile(sf):
            try:
                with open(sf) as f:
                    current = json.load(f).get("session", "global")
            except (json.JSONDecodeError, OSError):
                pass
        try:
            session = next(
                (
                    item
                    for item in _list_all_sessions()
                    if item.get("name", item.get("id")) == name
                ),
                None,
            )
        except RuntimeError as e:
            print(f"Error loading session: {e}", file=sys.stderr)
            return
        if session is None:
            print(f"Session not found: {name}", file=sys.stderr)
            return
        details = dict(session)
        details["active"] = current == name
        print(json.dumps(details, indent=2, sort_keys=True))

    else:
        print(f"Unknown session subcommand: {sub}", file=sys.stderr)
        sys.exit(1)


# ── forget ────────────────────────────────────────────────────────────────

def cmd_forget(args: list[str]):
    """Delete observations."""
    if not args:
        print("Usage: forget <id> | forget --query <q> | forget --session <name>", file=sys.stderr)
        sys.exit(1)

    if args[0] == "--query" and len(args) > 1:
        query = " ".join(args[1:])
        # Search for matching conclusions
        results = _api("POST", f"/v3/workspaces/{WORKSPACE}/conclusions/query", {
            "query": query,
            "top_k": 10,
            "filters": {"observer": OBSERVER, "observed": OBSERVED},
        })
        if not results:
            print("No matching observations found.")
            return
        print(f"Found {len(results)} matching observation(s):")
        for c in results:
            print(f"  [{c.get('id', '?')}] {c.get('content', '')[:80]}")
        print("\nTo delete a specific observation: forget <id>")

    elif args[0] == "--session" and len(args) > 1:
        session_name = args[1]
        count = 0
        while True:
            results = _api(
                "POST",
                f"/v3/workspaces/{WORKSPACE}/conclusions/list?size=100&page=1",
                {
                    "filters": {
                        "observer_id": OBSERVER,
                        "observed_id": OBSERVED,
                        "session_id": session_name,
                    },
                },
            )
            items = results.get("items", []) if isinstance(results, dict) else []
            if not items:
                break
            deleted_this_page = 0
            for c in items:
                cid = c.get("id")
                if cid:
                    try:
                        _api(
                            "DELETE",
                            f"/v3/workspaces/{WORKSPACE}/conclusions/{cid}",
                        )
                        count += 1
                        deleted_this_page += 1
                    except RuntimeError as e:
                        print(f"  Failed to delete {cid}: {e}", file=sys.stderr)
            if deleted_this_page == 0:
                break
        if count == 0:
            print(f"No observations found for session '{session_name}'.")
            return
        print(f"Deleted {count} observation(s) from session '{session_name}'.")

    else:
        # Delete by ID
        cid = args[0]
        try:
            _api("DELETE", f"/v3/workspaces/{WORKSPACE}/conclusions/{cid}")
            print(f"Deleted observation {cid}.")
        except RuntimeError as e:
            print(f"Error deleting {cid}: {e}", file=sys.stderr)
            sys.exit(1)


# ── config ────────────────────────────────────────────────────────────────

def cmd_config(args: list[str]):
    """Show or update connection config."""
    if not args or args[0] == "show":
        print(f"Honcho API URL:  {HONCHO_BASE}")
        print(f"Workspace:       {WORKSPACE}")
        print(f"Observer peer:   {OBSERVER}")
        print(f"Observed peer:   {OBSERVED}")
        print(f"Docker Compose:  {os.path.join(_honcho_dir(), 'docker-compose.yml')}")
        sf = _session_file()
        session = "global"
        if os.path.isfile(sf):
            try:
                with open(sf) as f:
                    session = json.load(f).get("session", "global")
            except (json.JSONDecodeError, OSError):
                pass
        print(f"Active session:  {session}")
    else:
        print("Config modification is done via .env file in .claude/honcho/")
        print(f"Edit: {os.path.join(_honcho_dir(), '.env')}")


# ── main ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "setup": cmd_setup,
    "status": cmd_status,
    "session": cmd_session,
    "forget": cmd_forget,
    "config": cmd_config,
}


def main():
    if len(sys.argv) < 2:
        print("Honcho Memory Manager")
        print()
        print("Subcommands:")
        print("  setup                    Bootstrap Docker sidecar")
        print("  status                   Health check and stats")
        print("  session map <name>       Bind to a Honcho session")
        print("  session list             List all sessions")
        print("  forget <id>              Delete observation by ID")
        print("  forget --query <q>       Find observations to delete")
        print("  forget --session <name>  Wipe session observations")
        print("  config show              Show connection config")
        sys.exit(0)

    cmd = sys.argv[1]
    handler = COMMANDS.get(cmd)
    if not handler:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        print(f"Available: {', '.join(COMMANDS.keys())}", file=sys.stderr)
        sys.exit(1)

    handler(sys.argv[2:])


if __name__ == "__main__":
    main()
