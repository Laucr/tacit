# EDGAR Data Sources — Endpoints, URL Shapes, Access Rules

All endpoints below are **public SEC EDGAR** services. They require **no API key**. They do require a descriptive `User-Agent` header and respect a fair-access rate limit. This skill supplies the endpoints and field maps; the runtime's web/fetch tool performs the actual HTTP.

## 1. Ticker → CIK resolution

- **Ticker map (JSON):** `https://www.sec.gov/files/company_tickers.json`
  - Object keyed by row index; each value has `cik_str` (integer CIK), `ticker`, `title`.
  - Zero-pad the CIK to 10 digits for the submissions API: `str(cik_str).zfill(10)` → e.g. `320193` → `0000320193` (Apple).
- **Alternate map with exchange:** `https://www.sec.gov/files/company_tickers_exchange.json`.
- A ticker may be absent; fall back to full-text search and confirm the CIK from the filer header. Keep multiple CIKs distinct.

## 2. Submissions API (per-filer recent filings)

- **URL:** `https://data.sec.gov/submissions/CIK##########.json`.
- Returns issuer metadata plus `filings.recent`, a columnar object where keys are parallel arrays: accessionNumber, form, filingDate, reportDate, acceptanceDateTime, primaryDocument, primaryDocDescription, items, isXBRL, etc.
- Older filings overflow into paged files listed under `filings.files[].name`; fetch those via `https://data.sec.gov/submissions/<name>`.
- Forms of interest: 8-K, 4, SC 13D, SC 13G, 13F-HR, S-1, and `/A` amendments.

## 3. Full-text search

- `https://efts.sec.gov/LATEST/search-index?q=<query>&forms=<form>&dateRange=custom&startdt=YYYY-MM-DD&enddt=YYYY-MM-DD`
- Response `hits.hits[]` carry `_source` and `_id` in `<accession>:<primary_doc>` form.

## 4. Filing index & documents

- Filing index: `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<cik>&type=<form>&owner=include&count=40&output=atom`
- Accession folder: `https://www.sec.gov/Archives/edgar/data/<cik>/<accession-nodashes>/`; `index.json` lists documents.
- Parse Form 4 ownershipDocument XML and 13F INFORMATION TABLE XML for reliable fields.

## 5. Access rules

- Send a descriptive generic `User-Agent`, never a hardcoded secret or another person's private contact.
- Stay below the ~10 requests/second cap; throttle conservatively and cache maps/submissions.
- On 403/429, exponential backoff and report partial coverage.

## 6. Graceful degradation

- Missing CIK or empty result: report no matching public filings, never fabricate rows.
- Parse failure: keep partial fields, mark `parse_incomplete=true`, and continue.
