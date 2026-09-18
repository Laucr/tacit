# Methodology — Parsing, Field Maps, Dedup, Date Semantics, Pitfalls

This playbook defines what to extract, how to deduplicate, how to represent amendments, and how to preserve date semantics. Every produced row must carry `accession`, `form_type`, `source_url`, `filing_date`, and `event_or_period_date`.

## 1. Pipeline

```
ticker/insider/fund → CIK → enumerate filings → fetch primary doc → parse fields
   → normalize dates → dedup by accession → apply /A supersede → timeline + dataset
```

## 2. Form maps

### Form 4

Parse `ownershipDocument` XML. Keep issuer, reporting owner, relationships, Table I non-derivative rows, and Table II derivative rows separate. Capture transaction date, code, shares, price, acquired/disposed code, post-transaction ownership, direct/indirect ownership, and derivative exercise/conversion/expiration fields.

Codes are recorded verbatim: `P` purchase, `S` sale, `A` award, `M` exercise/conversion, `F` tax withholding, `G` gift, `C` conversion, `X` exercise, `D` disposition, `J` other. Do not editorialize into a buy/sell call.

### 13F-HR

Capture manager, quarter-end period, totals, and INFORMATION TABLE rows: issuer, class, CUSIP, value, shares/principal, SH/PRN, put/call, discretion, voting authority. Note that 13F is long US-listed positions only and up to 45 days stale.

### 8-K

Capture item numbers and event date separately from filing date.

### 13D / 13G

Capture issuer, reporting persons, percent of class, aggregate amount, reporting-person type, and active/passive purpose. Keep amendments and chains.

### S-1

Capture registrant, offering/security type, and amount registered when present.

## 3. Dedup and amendments

Accession number is the unique key. Keep `/A` amendments, mark the original `superseded_by`, and mark the amendment `is_amendment=true` and `amends=<original>`.

## 4. Date semantics

Keep filing/acceptance date, event/period date, and report date distinct. A filing-date timeline answers when the public learned; an event-date timeline answers when it happened. State the ordering used.

## 5. Pitfalls

Missing User-Agent, rate limits, mixed filing/event dates, dropped amendments, collapsed Form 4 codes, merged derivative/non-derivative tables, merged CIKs, 13F staleness, and full-text coverage starting in 2001 are all reportable pitfalls.

## 6. Graceful degradation

Report partial coverage and `parse_incomplete=true` on parse failures; say plainly when no results exist; do not guess ambiguous CIKs. This is collection, not analysis.
