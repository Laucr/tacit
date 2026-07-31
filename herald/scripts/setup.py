#!/usr/bin/env python3
"""
herald/scripts/setup.py

Check or create the herald config file at $HOME/.config/tacit-skills/herald.yaml.

Config schema (tiny — one key for now):

    # Where rendered HTML goes. Each workspace gets its own subfolder under here:
    #   <output_dir>/<workspace>-<branch>-<hash4>/      (when input is in a git repo)
    #   <output_dir>/<workspace>-<docker-name>/         (when no VCS info is available)
    output_dir: ~/www/html

The file lives under `~/.config/tacit-skills/` alongside other tacit-skills local
configs (XDG-ish style). We don't depend on PyYAML — the format is simple
`key: value` lines and a tiny stdlib parser handles it.

Usage:
    python setup.py             # show or create with defaults; print active path
    python setup.py --check     # exit 0 if config exists, 1 otherwise
    python setup.py --print     # print the active config to stdout
    python setup.py --force     # overwrite an existing config with defaults
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

CONFIG_PATH = Path(os.path.expanduser("~/.config/tacit-skills/herald.yaml"))
LEGACY_CONFIG_PATH = Path(os.path.expanduser("~/.config/.herald.yaml"))

DEFAULT_CONFIG = """\
# herald — output configuration
#
# output_dir: where rendered HTML lives. Each workspace gets its own subfolder:
#   <output_dir>/<workspace>-<branch>-<hash4>/     (input is in a git repo)
#   <output_dir>/<workspace>-<docker-name>/        (no VCS info available)
#
# Tilde and $HOME are expanded. Defaults to ~/www/html so a local
# `python -m http.server` from that dir serves every report.
output_dir: ~/www/html
"""


def parse(text: str) -> dict[str, str]:
    """Parse a tiny `key: value` YAML subset. Comments after `#`, blank lines OK."""
    cfg: dict[str, str] = {}
    for raw in text.splitlines():
        ln = raw.split("#", 1)[0].strip()
        if not ln or ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        cfg[k.strip()] = v.strip().strip("\"'")
    return cfg


def load() -> dict[str, str]:
    """Return parsed config, or {} if the file doesn't exist."""
    if not CONFIG_PATH.is_file():
        return {}
    return parse(CONFIG_PATH.read_text(encoding="utf-8"))


def ensure(force: bool = False) -> tuple[Path, bool]:
    """Create the config if it doesn't exist (or `force`). Returns (path, created?).

    If a legacy config exists at ~/.config/.herald.yaml and the new path is
    empty, migrate it in place (one-time, automatic).
    """
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists() and not force:
        return CONFIG_PATH, False
    if not force and LEGACY_CONFIG_PATH.is_file() and not CONFIG_PATH.exists():
        # one-time migration from ~/.config/.herald.yaml
        CONFIG_PATH.write_text(LEGACY_CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            LEGACY_CONFIG_PATH.unlink()
        except OSError:
            pass
        print(f"herald: migrated legacy config {LEGACY_CONFIG_PATH} → {CONFIG_PATH}", file=sys.stderr)
        return CONFIG_PATH, True
    CONFIG_PATH.write_text(DEFAULT_CONFIG, encoding="utf-8")
    return CONFIG_PATH, True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="herald-setup", description=__doc__)
    p.add_argument("--check", action="store_true", help="Exit 0 if config exists, 1 otherwise.")
    p.add_argument("--print", dest="do_print", action="store_true", help="Print the active config.")
    p.add_argument("--force", action="store_true", help="Overwrite existing config with defaults.")
    args = p.parse_args(argv)

    if args.check:
        if CONFIG_PATH.is_file():
            print(f"herald: config OK at {CONFIG_PATH}")
            return 0
        print(f"herald: no config at {CONFIG_PATH}", file=sys.stderr)
        return 1

    if args.do_print:
        if not CONFIG_PATH.is_file():
            print(f"herald: no config at {CONFIG_PATH} (run setup.py to create one)", file=sys.stderr)
            return 1
        sys.stdout.write(CONFIG_PATH.read_text(encoding="utf-8"))
        return 0

    path, created = ensure(force=args.force)
    if created:
        action = "Wrote default config" if args.force else "Created config"
        print(f"herald: {action} at {path}")
    else:
        print(f"herald: config already at {path} (use --force to reset)")
    cfg = load()
    out = cfg.get("output_dir", "~/www/html")
    print(f"  output_dir: {out}  (resolves to: {os.path.expanduser(out)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
