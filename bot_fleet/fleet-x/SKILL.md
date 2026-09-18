---
name: fleet-x
description: >-
  Use when a fleet bot needs X/Twitter watchlist posts for digests or alerts —
  always XFlux via fleet-x/fetch.py; never invent another X provider without an
  explicit user pick.
---
# Fleet X (XFlux)

Canonical fetcher: `/home/box/agent-data/fleet-x/fetch.py`  
Docs: `/home/box/agent-data/fleet-x/README.md`

## Provider rule
- **Always XFlux** (`https://www.xfluxapi.com/`) for standing watchlist pulls.
- Secret: `XFLUX_API_KEY` via fleet-secrets — never print it.
- Do **not** use official X API, user-X MCP, or a third-party hop unless the user explicitly picks a different provider.
- Each successful XFlux call burns monthly quota — prefer one batched morning fetch over scatter calls.

## Usage
```bash
# Core Cooper watchlist (default handles)
python3 /home/box/agent-data/fleet-x/fetch.py --limit 8 --markdown

# Custom handles
python3 /home/box/agent-data/fleet-x/fetch.py --handles karpathy,trq212,elonmusk --limit 5 --json
```

## Standing digest pattern (e.g. morning brief)
1. Load key through fleet-secrets (local-first).
2. Run `fleet-x/fetch.py` once for the watchlist.
3. If X is quiet, still note which handles were quiet — do not invent posts.
4. Midday alerts: prefer web/press; one targeted XFlux fetch only when something X-specific clears the bar.

## Anti-jobs
- Do not “try another X provider” when XFlux fails — report the failure and fix secrets / quota.
- Do not paste API keys or raw auth headers into chat or Trello.

## Permalink + freshness (digests)
XFlux tweet ids often 404 on x.com status URLs. `fetch.py` falls back to profile URLs (`https://x.com/{handle}`, marked `(profile)`). Never invent status URL templates from XFlux ids.

**For digests (Cooper morning brief and similar):**
1. **Freshness** — only cite posts inside the briefing window (~last 24h / since the prior run). Do not backfill with older “related” posts as evidence for today’s takes.
2. **Evidence** — profile links are not enough for a specific take. Before citing, verify an openable `https://x.com/{handle}/status/{id}` (FxTwitter/HTTP or official API `url`).
3. If a fresh take has no openable permalink, omit it or mark unresolved — never substitute an older post, never ship a broken status link.
