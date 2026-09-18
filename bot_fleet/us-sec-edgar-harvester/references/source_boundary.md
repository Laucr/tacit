# Source Boundary

This skill harvests **public SEC EDGAR** data only.

Allowed sources:

- Public SEC EDGAR endpoints: full-text search (`efts.sec.gov`), the submissions API (`data.sec.gov`), the ticker map (`sec.gov/files/company_tickers.json`), and the public filing index/document archive (`sec.gov/Archives/edgar/...`).
- Public filings, exhibits, and their structured XML/HTML documents.
- User-provided exports, CIK lists, or notes.

Not allowed:

- Any paywalled or member-only vendor feed presented as if it were EDGAR.
- Private messages, private datasets, or confidential documents.
- Fabricated filings, accession numbers, or fields not present in the source document.

Access conditions:

- Send a descriptive, generic `User-Agent`; never a secret, token, or a real person's private contact unless the user explicitly supplies their own.
- Respect SEC fair-access rate limits (~10 req/s cap; throttle in practice). On 403/429, back off and report partial coverage.

This is a pure information-collection skill: it organizes public facts with full source and date provenance. It does not analyze, value, or advise. 不构成任何投资建议 / does not constitute investment advice.
