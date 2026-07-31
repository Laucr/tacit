#!/usr/bin/env python3
"""
honcho_remember.py — Save observations to Honcho.

Reads a JSON array of observation strings from stdin, POSTs them as
conclusions to the Honcho API. Reads the active session from session.json.

Usage:
    echo '["User prefers uv over pip", "User is migrating to Vitest"]' | python honcho_remember.py
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

# Locate session.json.
# Priority: HONCHO_HOME env var > project-local .claude/honcho/ > ~/.honcho (global default)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_HONCHO_HOME = os.environ.get("HONCHO_HOME", "")
_GLOBAL_DEFAULT = os.path.join(os.path.expanduser("~"), ".honcho")


def _find_session_file() -> str:
    """Find session.json by checking known locations."""
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
    """Read the active session name from session.json, default to 'global'."""
    path = _find_session_file()
    if path:
        try:
            with open(path) as f:
                data = json.load(f)
                return data.get("session", "global")
        except (json.JSONDecodeError, OSError):
            pass
    return "global"


def _api(method: str, path: str, body: dict | None = None) -> dict:
    """Make an HTTP request to the Honcho API."""
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


def main():
    # Read observations from stdin
    raw = sys.stdin.read().strip()
    if not raw:
        print("No observations provided on stdin.", file=sys.stderr)
        sys.exit(1)

    try:
        observations = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON on stdin: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(observations, list) or len(observations) == 0:
        print("Expected a non-empty JSON array of observation strings.", file=sys.stderr)
        sys.exit(1)

    session = get_active_session()

    # Ensure the session exists (idempotent create)
    try:
        _api("POST", f"/v3/workspaces/{WORKSPACE}/sessions", {"name": session})
    except Exception:
        pass  # Session already exists or will fail on the conclusions call

    # Build conclusions payload
    conclusions = []
    for obs in observations:
        content = obs if isinstance(obs, str) else obs.get("content", "")
        if not content:
            continue
        conclusions.append({
            "content": content,
            "observer_id": OBSERVER,
            "observed_id": OBSERVED,
            "session_id": session,
        })

    if not conclusions:
        print("No valid observations to save.", file=sys.stderr)
        sys.exit(1)

    # POST to Honcho
    result = _api("POST", f"/v3/workspaces/{WORKSPACE}/conclusions", {
        "conclusions": conclusions,
    })

    count = len(result) if isinstance(result, list) else 0
    print(f"Saved {count} observation(s) to session '{session}'.")


if __name__ == "__main__":
    main()
