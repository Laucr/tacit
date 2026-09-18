---
name: fleet-secrets
description: >-
  Use when any fleet bot needs a secret (Slack bot token, XFlux, Cloudflare,
  Infisical bootstrap), after a box wipe, or when the user says a secret rotated
  — local-first load with Infisical write-through.
---
# Fleet secrets

Canonical loader: `/home/box/agent-data/fleet-secrets/load.py`  
Config: `/home/box/agent-data/fleet-secrets/config.json`  
Also see `/home/box/agent-data/fleet-secrets/README.md`.

## Policy
1. **Local-first** — env, then `box-secrets.json` (`card.*` preferred, legacy `secrets.*` ok).
2. **On miss** — fetch Infisical (prod) and **write-through** to local `card.*`.
3. **Stale local is OK** — do not Infisical-first on every call.
4. **`--refresh` / `refresh=True` only when the user (or Lumino) says a secret changed** — or after a confirmed rotation.
5. **Never print secret values.** Presence checks print names + ok/source only.
6. **`INFISICAL_CLIENT_SECRET` is local bootstrap only** — never pulled from Infisical.

## Happy path (code)
```python
import importlib.util
spec = importlib.util.spec_from_file_location("fs", "/home/box/agent-data/fleet-secrets/load.py")
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
tok = mod.get_secret("SLACK_BOT_TOKEN", required=True)  # local-first
```

## CLI
```bash
# presence / which layer (no values)
python3 /home/box/agent-data/fleet-secrets/load.py --source SLACK_BOT_TOKEN XFLUX_API_KEY

# after a rotation only
python3 /home/box/agent-data/fleet-secrets/load.py --refresh SLACK_BOT_TOKEN
```

## After a box wipe
1. Ensure `INFISICAL_CLIENT_SECRET` is restored locally (secret-request / Lumino) — never paste in chat.
2. Run presence check for expected keys (names only).
3. On miss, normal `get_secret` write-throughs from Infisical; do not invent alternate stores.

## Anti-jobs
- Do not re-debate Infisical-first vs local-first — this skill is the answer.
- Do not ask the user to paste tokens into chat; use secret-request / existing store.
- Do not dump `box-secrets.json` contents into transcripts.
