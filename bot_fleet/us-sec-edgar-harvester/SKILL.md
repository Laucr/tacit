---
name: US SEC EDGAR harvester
description: >-
  Use when collecting US SEC EDGAR filings (8-K, Form 4, 13D/G, 13F, S-1),
  tracking insider or 13F activity from EDGAR, or building a sourced filing
  timeline for a US ticker from public data.
---
# US SEC EDGAR Harvester

Collect and structure US SEC EDGAR public filings (8-K, Form 4, 13D/13G, 13F, S-1) for a US-listed issuer, insider, or fund into a **deduplicated, sourced, dated filing timeline plus a structured dataset**. Information collection only — no scoring, ranking, forecasting, or advice. Every row must be traceable to an EDGAR accession number.

Reads **only public SEC EDGAR endpoints**. Prefer this skill for raw, citable EDGAR filings.

## Core Workflow

1. **Scope the request.** Subject = US ticker/company, insider (Form 4), or institutional manager (13F). Note form types and date window. Read `references/source_boundary.md`.
2. **Resolve identifier → CIK.** Map ticker via `https://www.sec.gov/files/company_tickers.json` or EDGAR full-text search. Keep zero-padded 10-digit CIK; label multiple CIKs separately.
3. **Enumerate recent filings.** Submissions API `https://data.sec.gov/submissions/CIK##########.json`, or full-text search `https://efts.sec.gov/LATEST/search-index` for insider/fund subjects. Filter: `8-K`, `4`, `SC 13D`, `SC 13G`, `13F-HR`, `S-1`, and `/A` amendments.
4. **Fetch and parse** (see `references/methodology.md`):
   - **Form 4** — owner, relationship, Table I/II rows (code, date, shares, price, A/D, post-txn ownership)
   - **13F-HR** — holdings table; period end
   - **8-K** — item numbers + event date
   - **13D / 13G** — reporting person, % of class, purpose (active vs passive)
   - **S-1** — registrant, offering type, amount when stated
5. **Distinguish dates.** Capture both filing/acceptance date and event/period date — never mix them.
6. **Dedup and supersede.** Key = accession number. `/A` marks `superseded_by` on the original; keep both.
7. **Emit timeline + dataset** with a factual coverage summary (gaps, rate-limit truncation).
8. **Validate.** `python scripts/validate_report.py <filing_timeline.md>`

## Output Contract

- `filings_dataset.csv` (or `.json`) — one row per filing or Form 4 transaction with at least: `accession`, `form_type`, `filer`/`reporting_owner`, `cik`, `subject_issuer`, `filing_date`, `event_or_period_date`, `is_amendment`, `superseded_by`, `source_url`, plus form-specific columns.
- `filing_timeline.md` — chronological entries with accession + EDGAR document URL.
- Concise factual summary only — **no ranking, valuation, or recommendation.**

## Data Sources

- Full-text search: `https://efts.sec.gov/LATEST/search-index`
- Submissions API: `https://data.sec.gov/submissions/CIK##########.json`
- Ticker map: `https://www.sec.gov/files/company_tickers.json`
- Archives: `https://www.sec.gov/Archives/edgar/data/<cik>/<accession>/`

Public, no-key. See `references/edgar-sources.md` and `references/methodology.md`. Use a descriptive generic `User-Agent` per SEC fair access; throttle; on 403/429 back off and report partial coverage.

## Boundaries

- Facts only — not investment advice.
- Public EDGAR only; no keys.
- License: GPL-3.0. Source: https://github.com/quantskills/skill-us-sec-edgar-harvester

## Installed companions

- `references/edgar-sources.md`, `references/methodology.md`, `references/source_boundary.md`
- `scripts/validate_report.py`
- `LICENSE`
