# bot_fleet

Grok Bot fleet skills — shared playbooks for the multi-agent desktop assistants (Dr Eggbot, Lumino, WSB, Prints, Cooper, Explainer, Writer, and friends).

This pack is **nested on purpose**. The rest of [tacit](../README.md) puts one Claude Code skill per top-level directory; these Grok Bot skills live together under `bot_fleet/` so they do not collide with that loader convention. Copy or symlink individual skill folders into a Grok Bot / Cursor skills directory as needed. They are **not** wired into `.scripts/install.sh` by default.

Curated by **Dr Eggbot** (Grok Bot).

## Skills

| Skill | Description |
| --- | --- |
| [fleet-secrets](./fleet-secrets/SKILL.md) | Local-first secret load with Infisical write-through (Slack, XFlux, Cloudflare, Infisical bootstrap). |
| [fleet-x](./fleet-x/SKILL.md) | X/Twitter watchlist posts for digests — always XFlux via `fleet-x/fetch.py`; verified permalinks only. |
| [wsb-ibkr-book](./wsb-ibkr-book/SKILL.md) | Pull newest IBKR Account Overview from Drive, parse to `book.json`, refresh only when the overview changes. |
| [writer-revision](./writer-revision/SKILL.md) | Structured clarity → structure → voice revision that keeps the author’s meaning, facts, and voice. |
| [us-earnings-prints-desk](./us-earnings-prints-desk/SKILL.md) | US earnings forecast, expected-move read, and defined-risk options decision ticket. |
| [us-sec-edgar-harvester](./us-sec-edgar-harvester/SKILL.md) | Collect and structure public SEC EDGAR filings into a sourced, dated timeline. |
| [create-viz](./create-viz/SKILL.md) | Publication-quality charts from query results or DataFrames (matplotlib / seaborn / plotly). |
| [nothing-design](./nothing-design/SKILL.md) | Nothing design system — only when the user explicitly asks for Nothing style. |

## Notes

- Paths inside some `SKILL.md` files still point at the live Grok Bot box (`/home/box/...`, `/workspace/...`). Treat those as runtime locations on the fleet machine, not as paths inside this git repo.
- Helper scripts under `*/scripts/` are reference copies; secrets and live account books are never committed here.
- Evidence links in X digests (`fleet-x`) must be verified openable post URLs within the briefing window — never invent status URLs from opaque ids.

## Author

Prepared for the Grok Bot fleet by **Dr Eggbot**.
