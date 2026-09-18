---
name: wsb-ibkr-book
description: >-
  Use when WSB (or fleet) needs the IBKR book from Google Drive — pull newest
  IBKR Account Overview, parse to /workspace/wsb-recap/book.json, or check
  whether the Drive file changed before refreshing.
---
# WSB IBKR book

Fast path for WSB routines to read the user’s IBKR book without waiting on a Drive hunt mid-recap.

Canonical files:
- Parser: `/workspace/wsb-recap/book_parse.py`
- Locked book: `/workspace/wsb-recap/book.json`
- One-line summary: `/workspace/wsb-recap/book.summary.txt`

## Discover newest overview (Google Drive)
1. Discover Google Drive tools each run.
2. `search_files` with query: `title contains 'IBKR Account Overview'`
3. Pick the newest by `modifiedTime`. Prefer a `(complete)` title when the same date ties.
4. Note `id`, `title`, `modifiedTime`, `viewUrl`.

## Status vs refresh
```bash
# What book.json currently points at
python3 /workspace/wsb-recap/book_parse.py status

# Compare to Drive metadata (exit 0 = needs refresh, 1 = current)
python3 /workspace/wsb-recap/book_parse.py needs-refresh \
  --drive-id '<fileId>' --drive-modified '<modifiedTime>'
```

**Pre-open routine rule:** only check status. Refresh (pull + parse + write) **only when** `needs-refresh` says so (newer/different overview, or missing book). Stay quiet when unchanged.

## Refresh (when needed)
1. Download overview content (`download_file_content` or `read_file_content`).
2. Write markdown to a temp path (e.g. `/tmp/ibkr-overview.md`).
3. Parse + write:
```bash
python3 /workspace/wsb-recap/book_parse.py write \
  --md /tmp/ibkr-overview.md \
  --source-title 'IBKR Account Overview ….md' \
  --source-id '<fileId>' \
  --source-modified '<modifiedTime>' \
  --source-url '<viewUrl>'
```
4. Consumers read `/workspace/wsb-recap/book.json` (equities, options, account, summary).

## Consumers
- **Pre-open (~09:50 ET weekdays):** status check; refresh only if overview moved.
- **Open+1h options check (10:30 ET weekdays):** read `book.json` for qty/credits/strikes; do not re-pull Drive unless book is missing.
- **US close recap:** read `book.json` for book sizes; do not hardcode stale qty/credits when the book exists.

## Anti-jobs
- Do not Infisical/Drive-spam every options mark check — use the local book.
- Do not invent positions when Drive is empty; say the overview is missing.
- Never print secrets; overview markdown has no account ids by design.
