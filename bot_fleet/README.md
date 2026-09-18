# bot_fleet

Shared Grok Bot fleet skills that are common and non-personal — safe to ship in the open [tacit](../README.md) toolkit.

This pack is **nested on purpose** so it does not collide with tacit's one-skill-per-top-level Claude Code loader convention. 

Curated by **Dr Eggbot** (Grok Bot).

## Skills

| Skill | Description |
| --- | --- |
| [fleet-secrets](./fleet-secrets/SKILL.md) | Local-first secret load with Infisical write-through (Slack, XFlux, Cloudflare, Infisical bootstrap). |
| [fleet-x](./fleet-x/SKILL.md) | X/Twitter watchlist posts for digests — always XFlux; verified permalinks only. |
| [writer-revision](./writer-revision/SKILL.md) | Structured clarity → structure → voice revision. |
| [create-viz](./create-viz/SKILL.md) | Publication-quality charts from query results or DataFrames. |

## Notes

- Paths inside some `SKILL.md` files still point at the live Grok Bot box (`/home/box/...`, `/workspace/...`). Treat those as runtime locations on the fleet machine.
- Helper scripts under `*/scripts/` are reference copies; secrets are never committed here.

## Author

Prepared for the Grok Bot fleet by **Dr Eggbot**.
