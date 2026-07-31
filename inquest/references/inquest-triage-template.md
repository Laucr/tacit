---
feature: <slug>
artifact: inquest
mode: triage
version: 1
prd_version: <PRD version at time of triage, or `unknown`>
plan_version: <plan version, or `unknown`>
bailiff_input: <path to the bailiff report being triaged, e.g. .claude/reports/<slug>-bailiff-r2.md>
bailiff_version: <version verified by that bailiff report, or `unknown`>
last_aligned: <today>
status: current
---

# Inquest Triage Report r<N>: <Feature Title>

**Spec:** .claude/prds/<slug>.md (v<prd_version>, or "unversioned legacy")
**Plan:** .claude/plans/<slug>.md (v<plan_version>, or "—")
**Bailiff input:** <bailiff_input> (v<bailiff_version>)
**Date:** <today>
**Recommendation:** re-run bailiff | run pivot for §<id> | investigate <env> | none

<!-- Frontmatter rules:
     - `mode: triage` distinguishes this report from smoke-mode inquest reports.
       See references/inquest-report-template.md for the smoke variant.
     - `bailiff_input` pins the exact bailiff artifact this run acted on.
       Never overwrite prior inquest reports — always write a fresh -r<N>.md. -->

## Triage summary

`fixed=<F> rejected=<R> deferred=<D>` — <one-line human-readable outcome>

<!-- Examples:
     `fixed=2 rejected=1 deferred=0` — every real finding closed, one false positive rejected.
     `fixed=0 rejected=3 deferred=0` — all findings triaged clean; bailiff verdict was noise.
     `fixed=1 rejected=0 deferred=2` — partial; one fix landed, two need design decisions. -->

## Findings

| # | Bailiff id | Source (PRD §) | File:line | Outcome | Evidence pointer |
|---|---|---|---|---|---|
| 1 | F1 | §6.2 | handler.go:214 | CONFIRMED_FIXED | grep re-run at HEAD; §Fixes row 1 |
| 2 | F2 | §7 | order_service.go:88 | REJECTED_NOT_REAL | code no longer matches bailiff's description as of <sha> |
| 3 | W1 | §4 | client.go:12 | CONFIRMED_DEFERRED | fix would touch >3 files; §Deferred row 1 |
| 4 | S1 | — | cmd/server.go:42 | CONFIRMED_FIXED | fmt.Println → log.Print; §Fixes row 2 |

<!-- Outcomes: CONFIRMED_FIXED | CONFIRMED_DEFERRED | REJECTED_NOT_REAL | REJECTED_SPEC | REJECTED_ENVIRONMENT
     Bailiff ids: F<n> = Failure/FAIL row; W<n> = WARN row; S<n> = Static Check row -->

## Fixes applied

<!-- One row per CONFIRMED_FIXED. Diff summary in one line — enough to identify
     the change; the actual diff is in git. Re-verification is the check that
     produced the finding, re-run at the new HEAD. -->

### Fix 1 — F1 (handler.go:214)

- **Diff:** `handler.go:214 — swap 500 → 404 on missing order`
- **Re-verification:** re-ran `go test ./handler -run TestMissingOrder` — passes; grep for `500` in surrounding scope returns nothing.
- **Closes finding:** F1 (§6.2)

### Fix 2 — S1 (cmd/server.go:42)

- **Diff:** `cmd/server.go:42 — replace fmt.Println with log.Print`
- **Re-verification:** grep `fmt.Println` in cmd/server.go returns nothing.
- **Closes finding:** S1

## Rejections

<!-- One block per REJECTED_* or CONFIRMED_DEFERRED. Evidence must be concrete:
     a grep result, a source excerpt, a config path, a §id — no hand-waving. -->

### Rejection 1 — F2, REJECTED_NOT_REAL

- **What bailiff claimed:** <one-sentence quote from bailiff report>
- **Evidence:** code at order_service.go:88 no longer matches bailiff's description as of commit <sha> — the referenced early return is gone. Bailiff likely ran against an older commit.
- **Suggested action:** none.

### Rejection 2 — W1, CONFIRMED_DEFERRED

- **What bailiff claimed:** <one-sentence quote>
- **Why deferred:** fix would require changes across `client.go`, `pool.go`, and `config.go` — package-scope, not triage-safe (see D2).
- **Suggested action:** open a design task; not blocking.

## Suggested next step

- [ ] <one specific action — re-run bailiff | run pivot for §<id> | investigate <env> | none>
- [ ] <if any fixes landed: re-run bailiff to confirm the verdict flips>
- [ ] <if any REJECTED_SPEC: run pivot against the named §id>

## Bailiff report status flip

- **Bailiff report:** <bailiff_input>
- **Prior status:** current
- **New status:** superseded | current (unchanged)
- **Sidecar fields written:** `superseded_by: <this report>`, `triage_outcome: <fixed|partial|clean|deferred>`, `triaged_at: <today>`, `findings_status: { F1: CONFIRMED_FIXED, F2: REJECTED_NOT_REAL, W1: CONFIRMED_DEFERRED, S1: CONFIRMED_FIXED }`

<!-- `findings_status:` is the machine-readable per-finding map — one entry per
     bailiff finding id (F<n>/W<n>/S<n>), value ∈ CONFIRMED_FIXED |
     CONFIRMED_DEFERRED | REJECTED_NOT_REAL | REJECTED_SPEC | REJECTED_ENVIRONMENT.
     Ordering follows bailiff's original report order. On re-triage, merge into
     any existing map — never delete keys. Full schema in PRD §6.5.1. -->

<!-- If the bailiff report lacked frontmatter and inquest ran under subagent
     transport, note the `> **Triaged by …**` notice that was prepended in
     lieu of frontmatter, and record `retrofit_gap: true`. In that case the
     `findings_status:` map is NOT written — the main agent must read this
     triage report's body for per-finding state. -->

## Unknowns

<!-- Anything the caller must resolve before the next step is safe.
     If nothing, write "None." -->

- <question / blocker>
