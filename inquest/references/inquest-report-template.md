---
feature: <slug>
artifact: inquest
mode: smoke
version: 1
prd_version: <version pinned at time of failure, or `unknown` if PRD has none>
plan_version: <plan version, or `unknown`>
bailiff_version: <last verification version, or `none` if no verifier ran>
last_aligned: <today>
status: current
---

<!-- This is the **smoke-mode** template — three-way diff (PRD ↔ code ↔ smoke).
     For the bailiff-triage variant, see references/inquest-triage-template.md.
     Mode is chosen at Step 1 of the inquest workflow. -->

# Inquest Report r<N>: <Feature Title>

**Spec:** .claude/prds/<slug>.md (v<version>, or "unversioned legacy")
**Surfaced in:** smoke | staging | prod | code-review
**Date:** <today>
**Diagnosis:** code-bug | spec-stale | spec-gap | environment

## What smoke saw

<1-3 sentences. If a log line, request, or stack trace was provided, quote it.>

## Drift status at time of failure

<!-- If plumb is available, paste its output for this feature.
     If not, write a one-line manual assessment:
       "PRD v3.7 (frontmatter), build report claims v3.3 — build is stale."
     If no version info exists at all:
       "Legacy artifacts; no version pins. Comparison done by content match." -->

```
<plumb output or manual assessment>
```

## Three-way diff

| Aspect | PRD says | Code does | Smoke saw |
|---|---|---|---|
| <observable behavior> | <quote, §<id>> | <one-liner, file:line> | <observed value> |
| <observable behavior> | <quote, §<id>> | <one-liner, file:line> | <observed value> |

## Diagnosis

<!-- One of:

  CODE BUG: PRD and smoke agree on expected behavior; code at <file:line> does
  something different. Spec stays. Fix code.

  SPEC STALE: Code matches what smoke saw. PRD describes older behavior
  the team moved past. Run pivot to update PRD; decide separately whether
  the code is now correct.

  SPEC GAP: PRD did not specify this case. Code does something arbitrary;
  smoke caught it. Run pivot to add the requirement, then decide whether
  the existing code satisfies it.

  ENVIRONMENT: PRD = code = bailiff verdict. Failure is in config, upstream
  input, or runtime environment. Spec is fine; investigate <where>.
-->

<the diagnosis paragraph for this case>

## Suggested next step

- [ ] <one specific action — fix file:line | run pivot | investigate config>
- [ ] <if pivot: re-run bailiff afterward>
- [ ] <if pivot: rebuild affected phases>

## Open questions

<!-- Anything unresolved that the user needs to decide.
     If nothing, write "None." -->

- <question>
