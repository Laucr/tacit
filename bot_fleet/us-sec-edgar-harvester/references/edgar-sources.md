# EDGAR Data Sources — Endpoints, URL Shapes, Access Rules

All endpoints below are **public SEC EDGAR** services. They require **no API key**. They do
require a descriptive `User-Agent` header and respect a fair-access rate limit. This skill
supplies the endpoints and field maps; the runtime's web/fetch tool performs the actual HTTP.

## 1. Ticker → CIK resolution

- **Ticker map (JSON):** `https://www.sec.gov/files/company_tickers.json`
  - Object keyed by row index; each value has `cik_str` (integer CIK), `ticker`, `title`.
  - Zero-pad the CIK to 10 digits for the submissions API:
    `str(cik_str).zfill(10)` → e.g. `320193` → `0000320193` (Apple).
- **Alternate map with exchange:** `https://www.sec.gov/files/company_tickers_exchange.json`.
- A ticker may be absent (foreign private issuers, funds); fall back to full-text search by
  company name and confirm the CIK from the filer header before harvesting.
- One legal entity can own **multiple CIKs** (historical names, subsidiaries). Keep each CIK
  distinct and labelled — do not silently merge.

## 2. Submissions API (per-filer recent filings)

- **URL:** `https://data.sec.gov/submissions/CIK##########.json` (10-digit padded CIK).
- Returns issuer metadata plus `filings.recent`, a **columnar** object where each key is a
  parallel array: `accessionNumber`, `form`, `filingDate`, `reportDate`, `acceptanceDateTime`,
  `primaryDocument`, `primaryDocDescription`, `items`, `isXBRL`, etc. Zip the arrays by index
  to reconstruct one record per filing.
- Older filings overflow into paged files listed under `filings.files[].name`; fetch those
  (`https://data.sec.gov/submissions/<name>`) if the requested window predates `recent`.
- `form` values of interest: `8-K`, `4`, `SC 13D`, `SC 13G`, `13F-HR`, `S-1`, and their
  `/A` amendments (`8-K/A`, `4/A`, `SC 13D/A`, `13F-HR/A`, `S-1/A`).

## 3. Full-text search (across filers — insiders, funds, phrases)

- **URL:** `https://efts.sec.gov/LATEST/search-index?q=<query>&forms=<form>&dateRange=custom&startdt=YYYY-MM-DD&enddt=YYYY-MM-DD`
  - The human UI at `https://efts.sec.gov/LATEST/search-index` is backed by this JSON API;
    the equivalent front-end is `https://www.sec.gov/cgi-bin/srqb` / `https://www.sec.gov/edgar/search/`.
- Response `hits.hits[]` each carry `_source` (form, filer, `file_date`) and `_id` of the
  shape `<accession>:<primary_doc>`. Split on `:` to recover the accession number.
- Full-text search covers filings from **2001 onward**; for older filings use the
  submissions API or the browse-EDGAR company page.

## 4. Filing index & documents

- **Filing index (JSON):** `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=<cik>&type=<form>&dateb=&owner=include&count=40&output=atom`
  (Atom/XML) — a per-company filing list alternative to the submissions API.
- **Accession folder:** `https://www.sec.gov/Archives/edgar/data/<cik>/<accession-nodashes>/`
  - `index.json` in that folder lists every document in the filing.
  - Accession numbers appear two ways: dashed `0000320193-24-000123` (canonical ID) and
    no-dash `000032019324000123` (used in the archive path). Normalize consistently.
- **Structured Form 4 XML:** the primary document is an XML `ownershipDocument`; parse it
  rather than the rendered HTML for reliable fields.
- **Structured 13F XML:** the holdings live in the `INFORMATION TABLE` XML exhibit, not the
  cover page.

## 5. Access rules (SEC fair-access policy)

- **Declared `User-Agent` is mandatory.** Send a descriptive UA, e.g.
  `QuantSkills EDGAR Harvester (contact: <user-provided email>)`. Never hardcode a secret,
  token, or another person's private contact. If the user gives no contact, use a generic
  descriptive UA (e.g. `QuantSkills EDGAR Harvester research tool`) — do **not** invent a
  fake personal email.
- **Rate limit: no more than ~10 requests/second**, and be polite in practice (throttle to a
  few per second for a research harvest). Exceeding it returns HTTP 403/429 and can get an IP
  temporarily blocked.
- Prefer `data.sec.gov` (JSON) and the pre-built `company_tickers.json` over scraping HTML.
- Cache the ticker map and per-CIK submissions locally within a run to avoid re-fetching.

## 6. Graceful degradation

- On 403/429: back off exponentially, reduce concurrency to one request at a time, and if it
  persists, report **partial coverage** with the exact window/forms that were and were not
  fetched — never silently drop data.
- On a missing CIK or empty result: state that no matching public filings were found for the
  subject and window, rather than fabricating rows.
- On a parse failure for one document: keep the filing in the dataset with the fields that
  did parse, flag the row `parse_incomplete=true`, and keep going.
