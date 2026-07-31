---
name: pivot
description: Handle a mid-flight requirements pivot. Reads the current PRD, captures the user's change in a delta document, edits the PRD in-place with a version bump, and marks the existing plan/build report/bailiff report as stale. Optionally re-emits the plan against the new PRD. Use this skill whenever the user says "the requirements changed", "update the PRD", "we need to pivot", "revise the spec", "scrap that approach, instead...", "the plan is wrong now", or otherwise indicates the spec must move while implementation is in flight. Also use when inquest or a code review surfaces a gap that requires the spec to change.
---

# Pivot

A formal correction to the spec. When requirements shift while implementation
is in flight, three artifacts go silently out of sync — the plan still describes
the old design, the build report was made against yesterday's PRD, and any
verification verdict is no longer valid. Pivot is the verb that does that
reconciliation: it edits the PRD in place with a version bump, captures the
*why* of the change in an append-only delta log, and marks downstream artifacts
stale so the next builder/verifier knows the floor moved.

Pivot pairs naturally with [[charter]] — both skills make formal corrections
to a project's authoritative documents, where charter governs the convention
record and pivot governs individual feature specs.

This skill is **standalone**: it does not require `blueprint` to have produced
the PRD, `builder` to have written the code, or `bailiff` / `plumb` to exist
at all. Pointed at any markdown file under `.claude/prds/<slug>.md` (or
`claude/prds/`, or even a raw path), it can capture a pivot, bump the PRD, and
log the delta.

It is also **legacy-tolerant**: PRDs without YAML frontmatter, with body-only
`**Version:** N.M` lines, or with mis-versioned downstream artifacts are all
handled. When frontmatter is missing, pivot offers to retrofit a single
frontmatter block on the way out — opt-in, never silent.

## Output Locations

- **PRD (edited in place):** `.claude/prds/<slug>.md` — version bumped, body updated.
- **Delta log:** `.claude/amendments/<slug>-r<N>.md` — append-only history of
  why each amendment happened, what changed, and what downstream artifacts it
  invalidated.
- **Plan (re-emitted):** `.claude/plans/<slug>.md` — only if the user opts into
  re-emit. Old plan goes to `status: superseded` first.
- **Existing build/bailiff reports:** `status` flipped from `current` to `stale`
  with a `stale_since: <prd version>` field added.

## When to use

Trigger phrases — explicit:

- "update the PRD", "the requirements changed", "we need to pivot"
- "the plan is wrong now", "scrap that approach, instead..."
- "ignore what we said earlier about X, do Y"

Trigger situations — implicit:

- During implementation, the user gives a new constraint that contradicts the plan.
- A smoke / staging failure surfaces a behavior gap that requires the PRD to change.
- A code review uncovers an assumption the PRD got wrong.
- A drift report flagged a stale plan but the PRD is right; this is the inverse —
  the PRD is the thing that needs to change.

If the change is a pure clarification (no impact on plan or implementation),
skip pivot and just edit the PRD with a minor version bump.

## What pivot does NOT do

- Does not re-run any builder. After pivot, the user decides whether to rebuild.
- Does not re-run any verifier. Existing verification reports are marked stale;
  the user re-runs verification deliberately when ready.
- Does not silently rewrite history. The pre-pivot PRD body is preserved in the
  delta log; the version bump and `last_aligned` tell you where to look.
- Does not require any other skill in the workflow. Each step below has a
  hand-rollable equivalent — pivot just sequences them and writes a delta.

## Workflow

### Step 1: Triage the change

Use `AskUserQuestion` to classify the pivot. The answer drives what gets bumped
and what gets invalidated.

| Class | Example | PRD bump | Plan | Build report | Bailiff |
|---|---|---|---|---|---|
| **Clarification** | adding an example, fixing a typo | minor (1.0 → 1.1) | leave as-is, sync `prd_version` | leave as-is, sync `prd_version` | leave as-is |
| **Additive** | new constraint that doesn't break existing work | minor | mark stale OR re-emit | mark stale | mark stale |
| **Pivot** | architectural change, dropped/replaced requirement | major (1.x → 2.0) | mark stale; re-emit recommended | mark stale | mark stale |

For clarification-class changes, prefer pointing the user at a direct PRD edit
rather than running pivot — it's overkill.

### Step 2: Read current state

1. Load `.claude/prds/<slug>.md` (fall back to `claude/prds/<slug>.md` if the
   repo doesn't use a leading dot). If the user gave an absolute path, use it.
2. Inspect the PRD's frontmatter:
   - **Frontmatter present:** read `version`, `last_aligned`, `status`. Use as-is.
   - **Frontmatter missing:** infer the current version from a body
     `**Version:** N.M` line. Default to `1.0` if no signal at all.
   - Use `AskUserQuestion` to confirm the inferred current version before bumping.
3. Locate any existing downstream artifacts: `.claude/plans/<slug>.md`,
   `.claude/reports/<slug>-build*.md`, `.claude/reports/<slug>-bailiff*.md`.
   Each may or may not have frontmatter; treat both cases.
4. If `plumb` is available in the workspace, run it for context — but
   do not require it. The same information is visible by reading the
   artifacts directly.
5. Load any existing `.claude/amendments/<slug>-r*.md` files (sorted) to
   understand prior pivots.

### Step 3: Capture the delta

Read `references/amendment-template.md` and write the new amendment to
`.claude/amendments/<slug>-r<N>.md` where N is the next integer. The template
captures:

- What changed in plain language (1-3 sentences)
- Source of the change (`user-feedback | discovery | smoke-failure | code-review | incident`)
- PRD sections affected (by stable §id)
- Old behavior → new behavior, concrete
- Downstream impact: which plan phases are now wrong/extra/missing, which
  build-report behaviors no longer match, which bailiff expectations are
  invalidated

The delta log is append-only. Never edit a prior amendment — write a new one
that supersedes it if needed.

### Step 4: Edit the PRD in place

1. **If the PRD has frontmatter:** bump `version` (minor for additive, major
   for pivot). Refresh `last_aligned` to today.
2. **If the PRD has no frontmatter:** offer to retrofit a minimal block on
   the way out. Use `AskUserQuestion`:
   - "Add YAML frontmatter to the PRD? (lets `plumb` / future amendments
     reason about versions precisely)"
   - Options: "Yes, add it", "No, keep as-is — bump body `**Version:**` line only"
   - If yes: prepend the canonical block (`feature`, `artifact: prd`, `version`,
     `last_aligned`, `status: current`) using the version *after* the bump.
   - If no: bump the body's `**Version:** N.M` line in place. Drift detection
     will still work via inference, just softer.
3. Edit the affected sections of the PRD body. Preserve stable §ids if they
   exist — if you're dropping §3.2, leave a `~~§3.2 (removed in v<N>)~~` stub
   so plans and reports referencing §3.2 still resolve. If you're adding a
   section, give it a fresh §id.
4. Add a one-line entry under a top-of-document `## Amendments` table (create
   the table if it doesn't exist):
   `| v3.7 | 2026-06-26 | r5 | switched backend from MCP to xsearch V2 |`
   linking to `amendments/<slug>-r5.md`.

The PRD is now the current snapshot. The amendment log is the history.

### Step 5: Mark downstream stale

For each existing `.claude/plans/<slug>.md`, `.claude/reports/<slug>-build*.md`,
`.claude/reports/<slug>-bailiff*.md`:

- **Artifact has frontmatter:**
  - Clarification class: sync the artifact's `prd_version` to the new PRD
    version. No `status` change.
  - Otherwise: set `status: stale` and add `stale_since: <new prd version>`.
    Do not touch the body — staleness is a metadata flag, not a content edit.
- **Artifact has no frontmatter:** offer to retrofit (same prompt as Step 4).
  - If user declines: append a single line near the top of the body —
    `> **Stale since PRD v<new>** — this <plan|build report|bailiff verdict>
    was last aligned to PRD v<old>.`
    Visible in any markdown reader; doesn't require frontmatter to read.

### Step 6: Optionally re-emit the plan

Use `AskUserQuestion`:
- "Do you want me to re-emit the plan now, or leave it stale?"
- Options: "Re-emit now", "Leave stale, I'll re-emit later", "I'll edit the plan by hand"

If re-emit:
1. Move the existing plan to `status: superseded` (keep the file).
2. Write a fresh `.claude/plans/<slug>.md` with bumped `version`,
   `prd_version` synced to the new PRD, `last_aligned` today.
3. The new plan should preserve unaffected phases verbatim where possible —
   the user already reviewed those. Only the affected phases get redesigned.

### Step 7: Confirm the result

Re-read the PRD's frontmatter (or the body `**Version:**` line if no
frontmatter was retrofitted) and confirm the new version is what you wrote.
If `plumb` is available, run it and paste the resulting table — but it is
optional, not required.

Surface to the user:
- What the new amendment says (link to `.claude/amendments/<slug>-r<N>.md`)
- What's now stale (build report, bailiff verdict)
- Suggested next step in plain language: "rebuild against the new plan",
  "re-run verification after rebuild" — phrased so it works regardless of
  which builder/verifier flow the user has.

### Step 8: Update the context ledger (if one exists)

If `.claude/memory/context-ledger.md` exists, append a one-line entry to the
**Blueprint** section:

```
- **{slug}** amended to v{new}: {1-line summary} (r{N}, stale: {build|bailiff|both})
```

If no context ledger exists, skip this step. The amendment log under
`.claude/amendments/` is the durable record; the context ledger is just a
shortcut for downstream skills that read it.

## The amendments/ directory

`.claude/amendments/<slug>-r1.md`, `<slug>-r2.md`, ... — append-only, one file
per pivot. Each file is small (the template is intentionally tight). The
PRD is the current snapshot; the amendment log is the why.

If the user asks "why is the PRD at v3.7?" — read the amendment log.

## Guidelines

- **One requirements change per run.** Don't bundle unrelated changes into one
  amendment file. If the user mentions two changes, write two amendments.
- **Preserve §ids when they exist.** Stable section IDs are the only
  mechanism that makes plan/report references survive a pivot. Removing an
  ID silently breaks those references. If the PRD doesn't use §ids, don't
  invent them mid-amendment — that creates churn for unclear benefit.
- **Never delete prior amendments.** The history is the value. If a prior
  amendment was a mistake, write a new amendment that supersedes it.
- **Stale is a metadata flag, not a body edit.** Mark `status: stale` (or
  drop a one-line stale notice if no frontmatter) — do not rewrite the
  report body. The body's job is to record what was built/verified at that
  PRD version.
- **Ask before re-emitting plans.** Re-emitting is destructive to the
  user's prior plan review.
- **Defer to a fresh design pass for greenfield.** If the pivot is so large
  that the existing PRD is mostly wrong, suggest starting over rather than
  trying to revise an entire document incrementally.
- **Standalone.** This skill works without any other skill. If the only
  thing you have is a hand-edited markdown PRD in `claude/prds/foo.md`,
  pivot still works on it.
