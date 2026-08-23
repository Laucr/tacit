---
feature: <slug>
artifact: bailiff
version: 1.0
prd_version: <prd version verified>
plan_version: <plan version verified>
last_aligned: <today>
status: current
---

# Bailiff Report: <Feature Title>

**Spec:** .claude/prds/<slug>.md
**Plan:** .claude/plans/<slug>.md (if applicable)
**Date:** <today>
**Verdict:** PASS / PARTIAL / FAIL

<!-- Frontmatter rules:
     - `prd_version` / `plan_version` = the versions verified in this report.
     - Drift-check flags this report as stale once the PRD/plan move past
       these versions. A stale PASS verdict no longer means "the spec is met."
     - `status` is one of: current | stale | superseded.
     - When re-running bailiff after a pivot, write a NEW report file
       (e.g. `<slug>-bailiff-r2.md`) and mark the old one `status: superseded`.
       Do not silently overwrite — the verification trail matters. -->

## Summary

<1-2 sentence overall assessment>

## Static Checks

| # | File | Line | Check | Severity | Message |
|---|---|---|---|---|---|
| 1 | cmd/server.go | 42 | logging | warning | fmt.Println found — use log package |
| 2 | cmd/server.go | 10 | local_paths | warning | Machine-local home path — replace with a relative path or config: /Users/***/proj |
| 3 | .claude/settings.json | 4 | secrets | error | Confidential literal (openai_key) |
| 4 | internal/store.go | 88 | prethink | warning | Redundant pre-thinking: recaps a discarded plan |

<!-- Universal checks (local_paths, secrets, prethink) always run.
     `error` rows (typically secrets) are Failures and block PASS.
     Secret `code` / message text must stay redacted. -->

## Expectation Results

| # | Expectation | Source (PRD §) | Status | Notes |
|---|---|---|---|---|
| 1 | CreateOrder returns 201 with order_id | §6.2 | PASS | |
| 2 | Missing order returns 404 | §7 | FAIL | Returns 500 instead |
| 3 | Timeout at 3s | §4 | SKIP | Not auto-testable |
| 4 | Mongo upsert on `trace_id` served by unique index | §Indexes | PASS | perf-pitfall #1 — index verified |
| 5 | Consumer `sub_batch_size == yaml_batch` | Plan Phase 2 | FAIL | perf-pitfall #3 — misalignment |

<!-- Performance-category expectations trace to references/perf-pitfalls.md
     by number so bailiff diffs across features can track which pitfalls
     keep recurring. -->

<!-- The "Source (PRD §)" column references stable section IDs from the PRD.
     This is what makes drift-mode bailiff possible — when §7 disappears
     between PRD versions, every expectation tagged §7 is auto-flagged. -->

## Failures

### F1: <Title>
- **Expectation:** <what the spec says>
- **Actual:** <what happens>
- **Source:** PRD §<id>
- **Diagnosis:** Missing implementation / Wrong behavior / Spec ambiguity

## Warnings

- <Naming mismatches between spec and implementation>
- <Things that passed but look fragile>
- <Code paths not covered by the spec>

## Test Files

- `path/to/test_file.go` — <what it covers>

## Suggested Fixes

- <Actionable fix for each failure>
