#!/usr/bin/env python3
"""
tacit-skills / migrate-configs.py

One-shot migrator. Walks every known legacy config location and relocates the
file into the unified `~/.config/tacit-skills/` root, where every tacit-skills
local config now lives.

Usage:
    python .scripts/migrate-configs.py            # do the migration
    python .scripts/migrate-configs.py --dry-run  # show what would move, change nothing
    python .scripts/migrate-configs.py --check    # exit 0 if nothing left to migrate, 1 otherwise

Idempotent. Safe to re-run. If both source and destination exist, the source
is left in place and a warning is printed (we never silently clobber).

Lives under `.scripts/` (a hidden directory) so the Claude Code skill loader
does not mistake it for a skill — every other top-level directory in this
repo is a skill, identified by its `SKILL.md`.

Adding a new migration:
    Append a tuple to LEGACY_MAPPINGS. Use absolute paths and skill-name
    keyed destinations under ~/.config/tacit-skills/.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_ROOT = Path(os.path.expanduser("~/.config/tacit-skills"))


def _expand(p: str | Path) -> Path:
    return Path(os.path.expanduser(os.path.expandvars(str(p)))).resolve()


# (skill, source path, destination path under ~/.config/tacit-skills/, note)
# Source can be absolute (a previous global location like ~/.config/.herald.yaml)
# or a path relative to the repo root (a previous in-skill config).
LEGACY_MAPPINGS: list[tuple[str, Path, Path, str]] = [
    (
        "herald",
        _expand("~/.config/.herald.yaml"),
        CONFIG_ROOT / "herald.yaml",
        "Pre-2026 herald global config.",
    ),
]


def plan() -> list[dict]:
    """Build a list of migration actions to perform."""
    actions: list[dict] = []
    for skill, src, dst, note in LEGACY_MAPPINGS:
        actions.append({
            "skill": skill,
            "src": src,
            "dst": dst,
            "src_exists": src.is_file(),
            "dst_exists": dst.is_file(),
            "note": note,
        })
    return actions


def render_status(action: dict) -> str:
    """Human-readable one-liner describing what will happen for this action."""
    skill = action["skill"]
    src = action["src"]
    dst = action["dst"]
    if action["dst_exists"] and not action["src_exists"]:
        return f"  [{skill}] OK   — already at {dst}"
    if action["dst_exists"] and action["src_exists"]:
        return f"  [{skill}] SKIP — both exist; refusing to overwrite. Resolve manually:\n           src: {src}\n           dst: {dst}"
    if not action["dst_exists"] and action["src_exists"]:
        return f"  [{skill}] MOVE — {src}\n             →  {dst}"
    return f"  [{skill}] —    — neither {src} nor {dst} exists; nothing to do"


def do_migrate(action: dict, dry_run: bool) -> tuple[bool, str]:
    """Perform a single migration. Returns (changed?, message)."""
    src: Path = action["src"]
    dst: Path = action["dst"]
    skill = action["skill"]
    if action["dst_exists"] and not action["src_exists"]:
        return (False, f"[{skill}] already migrated → {dst}")
    if action["dst_exists"] and action["src_exists"]:
        return (False, f"[{skill}] WARN: both src and dst exist, leaving alone (src={src}, dst={dst})")
    if not action["src_exists"]:
        return (False, f"[{skill}] nothing to migrate")
    if dry_run:
        return (True, f"[{skill}] DRY-RUN would move {src} → {dst}")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return (True, f"[{skill}] migrated {src} → {dst}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="migrate-configs", description=__doc__)
    p.add_argument("--dry-run", action="store_true",
                   help="Print what would happen without touching the filesystem.")
    p.add_argument("--check", action="store_true",
                   help="Exit 0 if nothing left to migrate, 1 if there are pending sources.")
    args = p.parse_args(argv)

    actions = plan()

    if args.check:
        pending = [a for a in actions if a["src_exists"] and not a["dst_exists"]]
        conflicts = [a for a in actions if a["src_exists"] and a["dst_exists"]]
        if not pending and not conflicts:
            print("tacit-skills: configs are up to date.")
            return 0
        if conflicts:
            print("tacit-skills: unresolved conflicts (both legacy and new exist):", file=sys.stderr)
            for a in conflicts:
                print(f"  - {a['skill']}: {a['src']}  vs  {a['dst']}", file=sys.stderr)
        if pending:
            print("tacit-skills: pending migrations:", file=sys.stderr)
            for a in pending:
                print(f"  - {a['skill']}: {a['src']}  →  {a['dst']}", file=sys.stderr)
        return 1

    print(f"tacit-skills config migrator — destination: {CONFIG_ROOT}")
    print()
    for a in actions:
        print(render_status(a))
    print()

    changed_any = False
    for a in actions:
        changed, msg = do_migrate(a, dry_run=args.dry_run)
        if changed or msg.startswith(f"[{a['skill']}] WARN"):
            print(msg)
        if changed:
            changed_any = True

    if not changed_any:
        print("Nothing to migrate. All configs already follow the convention.")
    elif args.dry_run:
        print()
        print("Dry-run complete. Re-run without --dry-run to perform the moves.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
