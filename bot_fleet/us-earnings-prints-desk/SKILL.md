---
name: US earnings prints desk
description: >-
  Use this when analyzing a US-listed stock earnings event for a forecast,
  expected-move read, and defined-risk options decision (pre-release ticket,
  flash, or postmortem).
---
# US earnings prints desk (adapted SOP)

Purpose: turn each earnings event into a documented forecast, a risk-bounded decision, and a measurable learning cycle. A strong business result does not guarantee a positive stock return or an options profit. **No trade is a completed decision.**

Lead every user-facing delivery with the trade ticket, not the memo: **decision → structure → max loss → EM vs hist → why**. Keep full business work in the archive; surface it only as support.

## Depth tiers

| Tier | When | Output |
| --- | --- | --- |
| A — full | High-conviction name, book overlap, or user asks for deep dive | Full source freeze, forecast, scenarios, options ticket, archive |
| B — fast ticket | Same-day ask or last tradable session | Event time, EM vs hist, thesis, primary + alt + no-trade, max loss, exits |
| C — scan | Calendar watch only | Date/time, days-to-print, EM vs hist gap, flag / pass |

Fundamentals may start at T−10; **lock the options call at T−1** (or the last regular session that can enter for BMO/AMC). Refresh event time, consensus, chain, and risk immediately before any ticket.

## Inputs required

Ticker/share class; fiscal quarter/year; confirmed event time (ET **and** analyst local time, with DST); report stage; price/data cutoff; horizon; holdings and existing options; willingness to receive/deliver shares; per-event loss budget; portfolio constraints.

Missing position inputs → research and illustrative structures only; no personalized contract count.

## Non-negotiables

- Facts, estimates, and judgments must be visibly distinct. Cite sources next to material figures.
- Never invent consensus, whispers, strikes, premiums, or “current suitability.” Mark gaps N/A.
- Rumors/whispers need a named source; otherwise omit.
- Expectations stack: frozen Street consensus → revision path → options-implied move → sourced whisper (optional).
- Business outcome ≠ market reaction ≠ options P&L. Separate them in every report.
- Defined-risk spreads are the default for speculative event trades. Naked short calls/strangles, uncovered ratios, and unmodeled calendars/diagonals are outside the default menu — if a crush thesis only works as a calendar, flag “needs separate model,” do not force a condor.
- Midprices are indicative; stress fills at bid/ask. Reject stale/crossed quotes or edge that dies after spreads/fees.
- Archive the pre-release memo and chain snapshot before the event; never overwrite with hindsight.

## Existing-position gate (before new speculative structures)

1. List current shares and options on the name (and highly correlated underlyings).
2. Score whether the print threatens those positions (gap through short strikes, assignment, forced delivery).
3. Decide hedge / roll / leave / reduce **first**.
4. Only then propose a new speculative structure, showing **incremental** risk and **combined** book risk.

## Pre-release workflow

### 1. Evidence baseline (Tier A; abbreviated on B)

- Confirm release timing on IR; pull release/presentation/webcast plans and latest SEC filings (20-F/6-K for foreign issuers).
- Comparable financials: ≥8 quarters when possible; 12–20 events for gap context when available.
- Freeze consensus (provider, timestamp, sample, mean/median, range, ~30d/90d revisions). Keep GAAP vs adjusted separate.
- Record each material input: metric | value | period | basis | source | pub time | retrieval time | fact/estimate/assumption.
- Five-sentence business model; name **three decisive metrics** and beat/miss thresholds.

### 2. Forecast and scenarios (Tier A; short form on B)

- Driver-based low/base/high → revenue/EPS/KPIs vs consensus and prior guide; next-quarter/FY outlook.
- Bear/base/bull: probability (sum 100%, labeled subjective unless calibrated), results+guide, next-session / 1–4w / 6–12m ranges, thesis trigger. Call out mixed outcomes (EPS beat + weak guide).
- Exit gate: base forecast, evidence for difference from consensus, beat/miss probability, confidence, falsifier. Keep long-term fair value separate from the earnings-gap forecast.

### 3. Options edge check

- Liquidity per leg: bid/ask, size, volume, OI, IV, Greeks, multiplier/deliverable, dividends, corporate actions, broker permissions.
- Synchronized stock/option snapshot in tradable hours. Compare first post-release expiry vs a longer holding expiry. Flag other catalysts in the window.
- **Straddle-cost move proxy** for near-ATM K: `(C + P) / S`. Label as life-of-option pricing proxy — not a guaranteed range or automatic 68% CI. Do not silently swap with `S × IV × √(days/365)`.
- Compare to split-adjusted historical absolute gaps (pre-close → next full close, and pre-close → expiry). Record median, upper tail, worst, sample size, regime breaks.
- Classify edge: directional surprise | move >/< priced | protection/share acquisition. IV crush can make a correct direction lose.
- Reprice at planned exit under stock scenarios × residual IV (low/base/high) and skew. Without trustworthy chain/model, mark next-day P&L unavailable; give expiration math only.
- Exit gate: edge after costs and tail stress, or **no trade** / separately justified hedge.

### 4. Structure menu (one primary, one alternative, no-trade baseline)

| Thesis | Candidate |
| --- | --- |
| Bullish surprise | Bull call debit spread |
| Bearish surprise | Bear put debit spread |
| Mildly bullish / rich downside | Bull put credit spread |
| Mildly bearish / rich upside | Bear call credit spread |
| Move < priced | Credit iron condor |
| Move > priced | Long straddle / strangle |
| Own shares; cap downside | Protective put / collar |
| Own shares; accept sale | Covered call |
| Want shares at a price | Cash-secured put (funded) |

Choose strikes from scenario outcomes and acceptable loss — delta alone is not event probability. Do not force income: shares + short call + extra short put increases downside.

### 5. Payoffs and sizing

- Compute max profit/loss, breakevens, expiration P&L; add fees/slippage to losses.
- Stress ±1× and ±2× move proxy, worst relevant historical gap, and a business-specific tail.
- Suggested speculative ceilings (calibrate, not targets): ≤0.5% NLV per event defined risk, ≤2% across concurrent earnings trades. **Always show incremental + combined with existing options/shares** — the ceiling alone can lie when short puts already embed event risk.
- `contracts = floor(event $ loss budget / (max loss per contract + cost allowance))`. If one contract exceeds budget, pass. Margin ≠ loss budget.
- For stock / covered calls / CSPs, stress full downside separately; reserve cash for intended put assignment.

### 6. Ticket, execute, manage

Trade ticket fields: ticker; event time ET+local; thesis; every leg; quote timestamp; entry limit; max gain/loss; BEs; hold period; residual-IV assumptions; scenario P&L; fees; assignment funding; profit target; invalidation; latest exit.

Enter only if edge survives the fill (multi-leg limit as a package). Stops are triggers, not guaranteed ceilings through gaps — size for full defined loss. Default: close event spreads before expiry while liquid unless assignment is deliberate and funded. A roll is a new trade: realize the loss and re-approve.

Timezone/broker overlay: state whether the analyst can manage through the US open/overnight gap; include assignment-funding and non-US account constraints on any ticket that can deliver shares.

## Post-release

1. **Flash (15–30m):** scorecard actual vs frozen consensus / own forecast / prior guide. Never mix adjusted consensus with GAAP actuals.
2. **After call:** demand, pricing, margins, capex, capital allocation; guide bridge; unanswered questions. Tone ≠ proof.
3. **24–48h / filing:** reconcile to statements; label provisional until 10-Q/10-K; update thesis and position action.
4. **Postmortem (T+5 to T+10):** separate forecast accuracy, market reaction, trading outcome. One concrete change: expected → actual → error source → next adjustment. Brier score across events when tracking binary calls.

## Per-event report skeleton

**A. Event and decision** — times ET/local; holdings; loss budget; decision in two sentences.

**B. Ticket (lead)** — quote time; stock; straddle proxy; hist moves; primary legs; alt / no-trade; contracts; max profit/loss; BEs; exits; incremental + combined risk.

**C. Business and forecast (support)** — three drivers; consensus vs own range; bear/base/bull table.

**D. Post-release** — scorecard; thesis status; action; forecast error; net P&L; one learning; source log.

## Partner boundaries

- Do not duplicate another desk’s daily US-close market recap; reuse shared session stats when available.
- Partner when an ER setup overlaps the shared book; otherwise stay in the prints lane.
