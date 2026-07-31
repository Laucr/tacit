#!/usr/bin/env python3
"""
honcho_recall.py — Retrieve observations from Honcho.

Queries Honcho's semantic search for conclusions relevant to a query.
Falls back to listing recent conclusions if semantic search returns nothing.

Usage:
    python honcho_recall.py "user's coding preferences"
    python honcho_recall.py --list                       # list all recent
"""

import json
import os
import sys
import urllib.error
import urllib.request


def _load_dotenv():
    """Auto-load ~/.honcho/.env into os.environ (only sets unset vars)."""
    for candidate in [
        os.environ.get("HONCHO_HOME", ""),
        os.path.join(os.path.expanduser("~"), ".honcho"),
    ]:
        env_file = os.path.join(candidate, ".env") if candidate else ""
        if env_file and os.path.isfile(env_file):
            with open(env_file) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, _, v = line.partition("=")
                        k, v = k.strip(), v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
            break


_load_dotenv()

HONCHO_BASE = os.environ.get("HONCHO_BASE_URL", "http://localhost:8787")
WORKSPACE = os.environ.get("HONCHO_WORKSPACE", "claude-code")
OBSERVER = os.environ.get("HONCHO_OBSERVER", "claude-code")
OBSERVED = os.environ.get("HONCHO_OBSERVED", "user")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_HONCHO_HOME = os.environ.get("HONCHO_HOME", "")
_GLOBAL_DEFAULT = os.path.join(os.path.expanduser("~"), ".honcho")


def _find_session_file() -> str:
    candidates = []
    # 1. Explicit env override
    if _HONCHO_HOME:
        candidates.append(os.path.join(_HONCHO_HOME, "session.json"))
    # 2. Project-local .claude/honcho/ (walk up from script dir)
    d = _SCRIPT_DIR
    for _ in range(10):
        candidates.append(os.path.join(d, ".claude", "honcho", "session.json"))
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    # 3. Global default: ~/.honcho/
    candidates.append(os.path.join(_GLOBAL_DEFAULT, "session.json"))
    for path in candidates:
        if os.path.isfile(path):
            return path
    return ""


def get_active_session() -> str:
    path = _find_session_file()
    if path:
        try:
            with open(path) as f:
                return json.load(f).get("session", "global")
        except (json.JSONDecodeError, OSError):
            pass
    return "global"


def _api(method: str, path: str, body: dict | None = None) -> dict | list:
    url = f"{HONCHO_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode() if e.fp else ""
        print(f"Error {e.code}: {err_body}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}", file=sys.stderr)
        print("Is Honcho running? Try: /honcho-manage setup", file=sys.stderr)
        sys.exit(1)


def format_conclusions(conclusions: list) -> str:
    """Format conclusions as a markdown list."""
    if not conclusions:
        return "No memories found."
    lines = []
    for c in conclusions:
        content = c.get("content", "")
        cid = c.get("id", "")
        session = c.get("session_id", "")
        created = c.get("created_at", "")[:10]  # date only
        meta = f" (id: {cid})" if cid else ""
        session_tag = f" [session: {session}]" if session else ""
        date_tag = f" ({created})" if created else ""
        lines.append(f"- {content}{session_tag}{date_tag}{meta}")
    return "\n".join(lines)


def semantic_search(query: str, session: str, top_k: int = 20) -> list:
    """Query conclusions via semantic search."""
    body: dict = {
        "query": query,
        "top_k": top_k,
        "filters": {
            "observer": OBSERVER,
            "observed": OBSERVED,
        },
    }
    result = _api("POST", f"/v3/workspaces/{WORKSPACE}/conclusions/query", body)
    return result if isinstance(result, list) else []


def list_recent(session: str, size: int = 30) -> list:
    """List recent conclusions (fallback when semantic search returns empty)."""
    body: dict = {
        "filters": {
            "observer_id": OBSERVER,
            "observed_id": OBSERVED,
        },
    }
    result = _api("POST", f"/v3/workspaces/{WORKSPACE}/conclusions/list?size={size}", body)
    # Paginated response
    if isinstance(result, dict) and "items" in result:
        return result["items"]
    return result if isinstance(result, list) else []


def main():
    if len(sys.argv) < 2:
        print("Usage: honcho_recall.py <query> [--list]", file=sys.stderr)
        sys.exit(1)

    session = get_active_session()

    if sys.argv[1] == "--list":
        conclusions = list_recent(session)
        header = f"## Stored Memories (session: {session})\n\n"
    else:
        query = " ".join(sys.argv[1:])
        conclusions = semantic_search(query, session)

        if not conclusions:
            # Fallback to listing recent
            conclusions = list_recent(session, size=10)
            if conclusions:
                header = f"## Memories (no semantic match for \"{query}\", showing recent — session: {session})\n\n"
            else:
                header = ""
        else:
            header = f"## Relevant Memories for: \"{query}\" (session: {session})\n\n"

    output = header + format_conclusions(conclusions)
    print(output)


if __name__ == "__main__":
    main()
