#!/usr/bin/env python3
"""
honcho_remember.py — Save observations to Honcho.

Reads a JSON array of observation strings from stdin, POSTs them as
conclusions to the Honcho API. Reads the active session from session.json.

Usage:
    echo '["User prefers uv over pip", "User is migrating to Vitest"]' | python honcho_remember.py
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import urllib.error
import urllib.request

_GLOBAL_DEFAULT = os.path.join(os.path.expanduser("~"), ".honcho")


def _honcho_dir() -> str:
    explicit = os.environ.get("HONCHO_HOME", "")
    if explicit:
        return os.path.abspath(os.path.expanduser(explicit))
    current = os.path.abspath(os.getcwd())
    for _ in range(10):
        candidate = os.path.join(current, ".claude", "honcho")
        if os.path.isdir(candidate):
            return candidate
        if os.path.isfile(os.path.join(current, "docker-compose.yml")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            break
        current = parent
    return _GLOBAL_DEFAULT


def _load_dotenv():
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

# Locate session.json.
# Priority: HONCHO_HOME env var > project-local .claude/honcho/ > ~/.honcho (global default)
def _find_session_file() -> str:
    """Find session.json by checking known locations."""
    path = os.path.join(_honcho_dir(), "session.json")
    return path if os.path.isfile(path) else ""


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
    with contextlib.suppress(Exception):
        _api("POST", f"/v3/workspaces/{WORKSPACE}/sessions", {"name": session})

    # Build conclusions payload
    conclusions = []
    for index, obs in enumerate(observations):
        if not isinstance(obs, str) or not obs.strip():
            print(
                f"Observation at index {index} must be a non-empty string.",
                file=sys.stderr,
            )
            sys.exit(1)
        content = obs.strip()
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
