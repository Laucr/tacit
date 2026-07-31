# Amendment r<N>: <One-line summary>

**Feature:** <slug>
**Date:** <today>
**PRD version:** <old> → <new>
**Class:** clarification | additive | pivot
**Source:** user-feedback | discovery | smoke-failure | code-review | incident

## What changed

<1-3 sentences in plain language. Lead with the decision. If the user gave
the change verbatim, quote it.>

## PRD sections affected

<!-- Reference stable §ids. If a section was added, list its new id.
     If a section was removed, list its old id with (removed). -->

- §3.2 — <how it changed>
- §4.1 (added) — <new section name>
- §5.0 (removed) — <reason>

## Old behavior → new behavior

<!-- Concrete, side-by-side. This is what a builder reading r<N> needs
     to understand exactly what to change. -->

| Aspect | Before | After |
|---|---|---|
| <thing> | <was> | <is now> |

## Downstream impact

### Plan

- Phase <N> (was: <old>) — <wrong | extra | unchanged | needs new step>
- New phase needed: <description>

### Build report

- <which behaviors recorded in the build report no longer match>
- <or: "no impact — purely additive">

### Bailiff verdict

- <which expectations are invalidated, by checklist item or §id>
- <or: "verdict still valid — clarification only">

## Why

<The motivation. Often the most valuable line in the file 6 months later.
"User found in smoke test that X failed when Y" / "Realized during impl
that Z assumption was wrong" / "Legal compliance review flagged X.">

## Suggested next steps

- [ ] Re-emit plan against new PRD
- [ ] Rebuild affected phases
- [ ] Re-run bailiff (after rebuild)
- [ ] <feature-specific>
