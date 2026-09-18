# Methodology — Parsing, Field Maps, Dedup, Date Semantics, Pitfalls

This is the harvesting playbook. It defines, form by form, which structured bits to extract,
how to deduplicate and supersede, how to treat dates, and the pitfalls that corrupt a naive
harvest. The goal is a **faithful, sourced, dated dataset of public facts** — not analysis.

## 1. The pipeline

```
ticker/insider/fund → CIK → enumerate filings (submissions API / full-text search)
   → for each accession: fetch primary doc → parse structured fields
   → normalize dates → dedup by accession → apply /A supersede → build timeline + dataset
```

Every produced row must carry: `accession`, `form_type`, `source_url`, `filing_date`,
`event_or_period_date`. A row without an accession number is not admissible.

## 2. Form-by-form field maps

### Form 4 — statement of changes in beneficial ownership (insider transactions)

Parse the `ownershipDocument` XML.

- **Header:** `issuer` (name, CIK, ticker); `reportingOwner` (name, CIK); relationship flags
  `isDirector`, `isOfficer`, `isTenPercentOwner`, `isOther` and `officerTitle`.
- **Table I — non-derivative** (`nonDerivativeTransaction`): `securityTitle`,
  `transactionDate`, `transactionCode`, `transactionShares`, `transactionPricePerShare`,
  `transactionAcquiredDisposedCode` (A/D), `sharesOwnedFollowingTransaction`,
  `directOrIndirectOwnership` (D/I).
- **Table II — derivative** (`derivativeTransaction`): same plus `conversionOrExercisePrice`,
  `exerciseDate`, `expirationDate`, `underlyingSecurity`. **Keep Table I and Table II separate** —
  merging option grants with open-market share buys is a classic error.
- **Transaction codes** (the `transactionCode` field) — capture the code verbatim; do not
  collapse them:
  - `P` — open-market or private **purchase** (cash out to buy shares).
  - `S` — open-market or private **sale**.
  - `A` — **grant/award** (e.g. RSU/stock award), often non-cash.
  - `M` — **exercise/conversion** of a derivative (option → shares).
  - `F` — shares **withheld to cover tax** on vesting.
  - `G` — **gift**.
  - `C` — conversion of a derivative; `X` — exercise of an in-the-money option;
    `D` — disposition to the issuer; `J` — other (see footnotes).
  - `P` and `S` are the economically informative open-market signals; `A`/`M`/`F`/`G` are
    compensation/mechanical. Record the code; **do not** editorialize it into a buy/sell call.

### 13F-HR — institutional holdings

- Cover page: `filingManager` (name, CIK), `periodOfReport` (quarter end), `tableEntryTotal`,
  `tableValueTotal`.
- **Information Table** (XML exhibit) — one row per holding: `nameOfIssuer`, `titleOfClass`,
  `cusip`, `value`, `shrsOrPrnAmt` (`sshPrnamt` + `sshPrnamtType` SH/PRN), `putCall`,
  `investmentDiscretion`, `votingAuthority` (Sole/Shared/None).
- 13F reflects **long US-listed positions as of the quarter end** — it omits shorts, cash,
  and non-US listings, and is filed up to 45 days after quarter end (stale by construction).

### 8-K — material event report

- Capture the **item numbers** from the submissions `items` field or the document headings,
  e.g. `1.01` (material agreement), `2.02` (results of operations), `5.02` (director/officer
  change), `7.01` (Reg FD), `8.01` (other events), `9.01` (exhibits). Record the set of items
  and the **event date** (item date), which differs from the filing date.

### 13D / 13G — beneficial ownership > 5%

- `subjectCompany` (issuer), `reportingPerson`(s), `percentOfClass`, `aggregateAmount`,
  `typeOfReportingPerson`. **13D** = active/control intent (10-day filing trigger);
  **13G** = passive/exempt investor. Amendments (`/A`) update the stake — always keep the
  amendment chain.

### S-1 — registration statement (offerings, IPOs)

- `registrant`, offering/security type, and amount registered when present on the cover.
  S-1 is often large and prose-heavy; extract only the cover/structured fields, not the body.

## 3. Deduplication and amendment supersede

- **Dedup key = accession number.** It is EDGAR's unique per-filing ID; never dedup on
  filer+date (a filer can file several forms the same day).
- **Amendments (`/A`):** an amended filing supersedes the original for the corrected facts.
  Keep both rows. On the original, set `superseded_by=<amendment accession>`; on the
  amendment, set `is_amendment=true` and `amends=<original accession>`. Do not delete the
  original — the audit trail matters.

## 4. Date semantics (the most common corruption)

Three distinct dates; label every row with which one it uses:

| Date | Meaning | Source |
| --- | --- | --- |
| `filing_date` / `acceptanceDateTime` | when EDGAR received/accepted the filing | submissions API `filingDate` / `acceptanceDateTime` |
| `event_or_period_date` | when the underlying event happened | Form 4 `transactionDate`, 8-K item date, 13F `periodOfReport`, 13D/G event date |
| `reportDate` | period covered (for periodic forms) | submissions `reportDate` |

A timeline ordered by filing date answers "when did the public learn"; ordered by event date
it answers "when did it happen". State which ordering the timeline uses. Never silently mix.

## 5. Pitfalls checklist

- **Missing/wrong User-Agent** → 403. Send a descriptive generic UA (see `edgar-sources.md`).
- **Rate-limit blocks** → throttle to a few req/s; back off on 429/403; report partial coverage.
- **Filing date vs event date** → keep both; label the timeline's ordering.
- **Amendments** → `/A` supersedes; keep the chain, never overwrite the original row.
- **Form 4 codes** → record `P/S/A/M/F/G/...` verbatim; don't reduce a grant/withhold to a "buy".
- **Derivative vs non-derivative** → keep Table I and Table II apart.
- **Multiple CIKs per entity** → keep distinct; don't merge subsidiaries into the parent.
- **13F staleness** → up to 45 days lagged, longs-only, US-listed-only; note it.
- **Full-text search coverage** → 2001-onward only; use submissions API for older filings.
- **This is collection, not analysis** → emit facts + sources; never a valuation or recommendation.

## 6. Graceful degradation

- Partial fetch → deliver what parsed, mark `parse_incomplete=true` / partial coverage, and
  state the exact forms/window missing.
- No results → say so plainly for the subject and window; do not fabricate.
- Ambiguous subject (name collision) → list the candidate CIKs and ask the user to disambiguate
  rather than guessing.

## 7. Relationship to sibling skills

`hk-us-insider-radar` and `hk-us-holder-concentration` answer similar questions from the
**Pandadata vendor feed** (normalized, cross-market, key-gated). This skill instead harvests
the **primary SEC public source** with full accession-level provenance. Use this one when the
user needs citable raw EDGAR filings; use the Pandadata skills for the vendor's normalized feed.
Do not invent Pandadata method signatures here — delegate any Pandadata call to `pandadata-api`.
