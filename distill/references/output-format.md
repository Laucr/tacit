# Output format: `bailiff-lessons-YYYY-MM-DD.md`

The digest file has four blocks in this exact order: header, sources list, numbered failure-mode categories, cross-cutting lessons. Match it verbatim — downstream tools and future distill runs diff against this shape.

## Filename

- Ends with `-YYYY-MM-DD.md` (today's date, ISO).
- Lives in the configured output folder (default `/root/.ai/harness/`).
- Idempotent per day: same-day re-runs overwrite the file, they don't append.

## Header block

```markdown
# Bailiff Lessons — Recurring Failure Modes and Guardrails (YYYY-MM-DD)

**Review date:** YYYY-MM-DD
**Cadence:** periodic — this is <first pass | pass N>. Subsequent reviews should be saved as
`bailiff-lessons-YYYY-MM-DD.md` alongside this file so drift over time stays visible.
**Corpus window:** all bailiff reports on disk as of YYYY-MM-DD, dated <earliest>
through <latest>.

<Short paragraph naming the repos covered and framing what each entry contains:
what the bailiff caught, why it slipped past `go build` / `mvn` / review,
and the guardrail that would have stopped it earlier.>
```

The H1 title must end with the date in parentheses. The three bold fields are fixed labels. The corpus-window dates come from the earliest and latest report-date fields extracted in Step 2.

## Sources list

```markdown
Sources referenced (path relative to `<doc-root>`, with the bailiff-report date each):

- `<repo>/claude/reports/<file>-bailiff.md` — YYYY-MM-DD
- `<repo>/claude/reports/<other>-bailiff.md` — YYYY-MM-DD
```

One line per bailiff file. Path is relative to the doc root, not absolute. Date is the report's own `**Date:**` line (or mtime, marked inferred). This list is the "what was covered" bookkeeping — it's what future distill runs diff against to detect added/retired reports.

Separator: a horizontal rule (`---`) between the sources block and the numbered categories.

## Numbered failure-mode categories

```markdown
## N. <Named failure mode — noun phrase, not a sentence>

**What happened.** <One concrete example, citing the bailiff by path and, if possible, exact identifier/line. If the same failure mode appeared in multiple reports, list each one.>

**Why it slipped past `go build` / `mvn` / review.** <The "how did this reach the bailiff at all?" analysis — the non-obvious part that motivates the guardrail.>

**Guardrail.**

- <Concrete, mechanically enforceable prevention.>
- <Bailiff-template addition, grep pattern, plan-phase requirement, invariant check.>
- <Not "be careful" — something a future skill or plan can actually run.>
```

Category names are short noun phrases (e.g. "The `Edit` tool over-match trap — duplicated legal code", "Framework defaults that silently violate the contract"). Numbering is sequential across the whole digest, not per-repo.

## Cross-cutting bailiff-workflow lessons

```markdown
---

## Cross-cutting bailiff-workflow lessons

### L1. <Short imperative or observation>.
<One or two sentences elaborating.>

### L2. <...>.
<...>
```

Prefixed `L1`, `L2`, … to distinguish from the numbered categories above. These are meta-observations about how bailiffs get used, not specific bugs — e.g. "compile is the floor not the ceiling", "static inspection is a coverage gap not a verification". Draw them from what actually recurs in the corpus, not boilerplate.
