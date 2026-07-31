---
feature: <slug>
artifact: build
version: 1.0
prd_version: <prd version this build implements>
plan_version: <plan version this build follows>
last_aligned: <today>
status: current
---

# Build Report: <Feature Title>

**Spec:** .claude/prds/<slug>.md
**Plan:** .claude/plans/<slug>.md
**Date:** <today>

<!-- Frontmatter rules:
     - `prd_version` and `plan_version` capture what the implementation was
       built against. Drift-check compares these to the live PRD/plan.
     - When the PRD or plan moves forward without a re-build, this report's
       status should flip to `stale`. The `pivot` skill does this for you.
     - `status` is one of: current | stale | superseded.
     - A new build report (after a re-build) gets a new `version` and a fresh
       `last_aligned`. The old report is moved to status: superseded. -->


## Summary

This build implements <thing> from the <slug> spec.

## Motivation

The spec called for <what the spec required>.
This matters because <why the feature exists — user impact or system impact>.

## Behavior

After this build:
- <exact behavior 1 — what the user or system now does>
- <exact behavior 2>
- <fallback / edge case behavior>

## Deviations from Plan

<!-- If you followed the plan exactly, write "None." and move on.
     If you diverged, state what changed and why — concretely.
     This is how the next person knows what the plan said vs. what actually shipped. -->

- <what the plan said → what you did instead, and why>

## Non-goals

This build does not:
- <thing intentionally left out, with a one-line reason>
- <another thing intentionally left out>

## Tradeoffs

<!-- Name the costs. If there's tech debt, say so. If performance is worse
     in some path, say so. If you chose simple-but-limited over clever-but-flexible,
     say so. Honest accounting prevents surprises downstream. -->

- <cost / ambiguity / performance / maintainability tradeoff>

## Implementation Notes

<!-- Key decisions a reviewer or future maintainer needs to understand.
     Not a line-by-line changelog — just the things that aren't obvious from the diff. -->

- <key implementation detail>
- <compatibility / migration / configuration note>

## Files Changed

<!-- One line per file. What changed and why. Enough to orient a reviewer. -->

- `path/to/file.go` — <what changed>

## Tests

Added/updated tests for:
- <case 1>
- <case 2>

## Open Items

<!-- Anything unresolved that the user should know about.
     If nothing, write "None." -->

- <open question or follow-up>

## Next Steps

- <suggested action — e.g., run tests, review changes, commit>
