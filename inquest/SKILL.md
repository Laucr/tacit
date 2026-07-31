---
name: inquest
description: Investigate a failure or a bailiff verdict against the spec. Two modes — **smoke** (post-deploy failure: three-way diff PRD ↔ code ↔ smoke, diagnosis only) and **triage** (bailiff report has open findings: verify each, fix real ones in place, reject the rest, flip the bailiff report's status). Use smoke mode when the user reports "smoke failed", "didn't work in staging", "broken in prod", "found a bug after deploy", or asks to "verify the fix landed", "did the patch work", "confirm the change reaches X". Use triage mode when the user says "triage the bailiff report", "check the bailiff findings", "fix the bailiff verdict", "work through the bailiff failures", or hands over a bailiff report path directly. Runs after a feature ships or after bailiff runs — not during initial build.
---

# Inquest

An official investigation into a failure — or into a bailiff verdict that
left findings on the table. Two modes, one skill:

- **Smoke mode** (existing) — the real world disagrees with the spec. Inquest
  builds a three-way diff (PRD says ↔ code does ↔ smoke saw) and hands back a
  diagnosis. Diagnosis only; never writes code.
- **Triage mode** (new) — bailiff produced a report with open findings.
  Inquest independently verifies each finding, applies a scoped fix where the
  finding is real, rejects the ones that aren't, and flips the bailiff
  report's metadata to reflect the outcome. Writes code, but only within
  files/functions the finding names.

Inquest pairs naturally with [[bailiff]]: bailiff is the court officer that
enforces the spec at build time; inquest is the formal hearing held after —
either when downstream evidence contradicts a passing verdict (smoke mode) or
when bailiff itself surfaced findings that need to be worked down (triage
mode).

The job of inquest is one of:

- The **spec** said one thing, the **code** does another → spec was right, code is buggy. *(smoke)*
- The **spec** said one thing, the **code** does the same thing, but **smoke** saw different → spec was wrong (missed a case). *(smoke)*
- The **spec** is silent on this case, the **code** does *something*, **smoke** says it's wrong → spec gap; needs a pivot pass. *(smoke)*
- The **spec** said it, the **code** does it, **verification** confirmed it, but **smoke** saw failure → environment/config issue, not a spec issue. *(smoke)*
- The **bailiff** flagged N findings — each is real (fix or defer), a false positive, a spec problem, or an environment quirk. *(triage)*

This skill is **standalone**: it does not require `bailiff`, `pivot`, or
`plumb` to be present. It reads whatever PRD / plan / build / verification
artifacts exist (frontmatter or not) and produces a diagnosis or triage
report. If only a PRD exists with no verification report at all, smoke mode
still works — the diagnosis just has fewer rows to compare.

It is also **legacy-tolerant**: PRDs without YAML frontmatter, build reports
that record version inline as `**Version:** N.M`, and missing `prd_version` /
`plan_version` references are all handled. The smoke/triage report itself
records whatever versions it could pin down (with `~` for inferred), so the
next reader knows what state the world was in when the incident happened.

## Output Location

- **Report:** `.claude/reports/<slug>-inquest-r<N>.md` where N is the next integer
  for this feature. Never overwrite a prior inquest report — smoke incidents
  and triage runs both stack.

## Subagent transport

`inquest` may be launched as a subagent from a main session — for
example, a session driving a post-deploy incident response loop or
the standard `blueprint → builder → bailiff → inquest → bailiff` loop.
The skill's behavior is unchanged; only the return contract differs.

A ready-made agent wrapper ships at `.agents/inquest.md` — install it
into your Claude Code agents directory (typically
`~/.claude/agents/inquest.md`) and the caller can invoke this transport
via `Agent(subagent_type: "inquest", ...)`. The wrapper is a thin shim
that invokes this skill and enforces the return contract below.

When invoked as a subagent:

- Do all normal work through Step 6. Load context, pick the mode, run the
  mode-specific workflow, write the report to
  `.claude/reports/<slug>-inquest-r<N>.md`, update the ledger in Step 8.
  Reports always stack — even a "no anomaly found" outcome is a distinct
  `-rN.md`.
- Skip Step 7's chat summary. Instead, **return exactly one line** to
  the caller, no preamble. The vocabulary depends on the mode:

  **Smoke mode:**

      wrote <path> — <diagnosis> (<suggested next step>)

  Diagnoses are one of `code-bug`, `spec-stale`, `spec-gap`,
  `environment`, or `inconclusive`. Example:
  `wrote .claude/reports/query-cache-inquest-r3.md — code-bug (fix at handler.go:214)`.

  **Triage mode:**

      wrote <path> — bailiff-triaged (fixed=<F> rejected=<R> deferred=<D> → <next step>)

  Where `<next step>` is one of `re-run bailiff`, `run pivot for §<id>`,
  `investigate <env>`, or `none`. Example:
  `wrote .claude/reports/query-cache-inquest-r4.md — bailiff-triaged (fixed=2 rejected=1 deferred=0 → re-run bailiff)`.

  **Failure sentinel (either mode):**

      could not diagnose — <one-sentence reason>

  Used for missing bailiff report, unreadable source, ambiguous mode,
  or a bailiff report already `status: superseded`.

- Never inline the three-way diff, the findings table, per-fix diffs,
  evidence, or diagnosis narrative into the return message. **The
  report on disk is the interface.** The main agent will read it before
  routing to `pivot`, re-running `bailiff`, or investigating the
  environment.
- Do not use `AskUserQuestion` from inside a subagent invocation. If
  Step 1's mode-selection or failure-anchoring detail is missing from
  the trigger message, record the ambiguity as an explicit "Unknowns"
  section in the report and let the main agent gather the missing
  detail on the next iteration.
- Do not invoke `pivot`, `bailiff`, or any other skill automatically —
  the return line names the recommended next step; the main agent
  decides whether to act on it. In triage mode specifically: do not
  `go test ./...` or run the project's full test suite after fixes —
  local re-verify is the ceiling (see B4).

## When to use

### Smoke mode — failure surfaced downstream

- "smoke failed", "smoke test broke"
- "didn't work in staging", "broken in prod", "issue in production"
- "found a bug after deploy"
- "the fix didn't land", "still broken"

Or fix verification against a live observation:

- "verify the fix", "did the patch work"
- "confirm the change reaches X", "is it actually doing Y now"

If the user reports a failure but no spec exists for the affected feature,
this skill is wrong — fall back to a normal debugging conversation.

### Triage mode — bailiff produced findings

- "triage the bailiff report", "check the bailiff findings"
- "fix the bailiff verdict", "work through the bailiff failures"
- User hands over a `.claude/reports/<slug>-bailiff*.md` path directly and
  asks to act on it
- A `<slug>-bailiff*.md` at `status: current` exists AND the user's message
  references its verdict but not a smoke/staging/prod failure

Under REPL, ambiguous cases get an `AskUserQuestion`; under subagent
transport, the presence of a bailiff report path in the trigger biases
toward triage. If neither a bailiff report nor a failure observation is
available, the skill is misapplied and it says so.

## Workflow

### Step 0: Load the context ledger

If `.claude/memory/context-ledger.md` exists, read it before starting work:

- **Blueprint** section — design rationale for the spec under investigation.
- **Builder** section — acknowledged divergences from the plan. These are
  known-and-accepted, not fresh findings.
- **Bailiff** section — prior verification verdicts. In triage mode, this is
  where the report under triage originated; in smoke mode, it tells you what
  was verified against which PRD version.

If the file doesn't exist, skip this step.

### Step 1: Mode selection

Decide **smoke** vs **triage** from the trigger content, per the "When to
use" table.

- **Under REPL** — if the mode is ambiguous (bailiff report exists AND user
  described a live failure), `AskUserQuestion` before continuing.
- **Under subagent transport** — infer, do not ask. If the trigger names a
  bailiff report path, choose triage; otherwise smoke. Record any residual
  ambiguity in the report's Unknowns section.

Then jump to **Mode A** (smoke) or **Mode B** (triage). Both modes rejoin
at Step 6.

---

## Mode A — Smoke investigation

Use when the trigger describes a downstream failure (smoke/staging/prod) or
asks to verify a fix landed against a live observation.

### Step A1: Anchor on the failure

Use `AskUserQuestion` to capture the minimum needed:

1. Which feature/spec slug is affected?
2. What was the observed behavior? (one or two sentences, ideally with a log line, request, or screenshot)
3. What was the expected behavior?
4. Where surfaced: smoke / staging / prod / code-review / other?

If the user already provided this in the trigger message, skip the question
and confirm what you parsed.

### Step A2: Load the spec triple

1. Read `.claude/prds/<slug>.md` (fall back to `claude/prds/<slug>.md` if the
   repo doesn't use the dot prefix). Note the current `version` — from
   frontmatter if present, from a body `**Version:** N.M` line otherwise,
   default `unknown` if neither.
2. Read `.claude/plans/<slug>.md` if present.
3. Read the latest `.claude/reports/<slug>-build*.md` if present.
4. Read the latest `.claude/reports/<slug>-bailiff*.md` (or any verification
   report) if present.
5. **If `plumb` is available**, run it for context — but treat it as
   optional. The smoke diagnosis comes from comparing what each artifact
   actually says, not from a precomputed alignment table.
   - If you can run it, anything STALE goes into the report — drift is often
     the root cause of "but the verifier passed!"
   - If you can't, do the manual comparison: does the build report claim to
     implement the same behavior the PRD currently describes? Does any
     existing verification report match the current PRD? If not, note the
     mismatch as drift evidence in the smoke report.

### Step A3: Snapshot current code

Read the implementation files. The strategy depends on what artifacts exist:

- **Build report exists, has frontmatter or a Files-Changed section:** start
  there. For each behavior the spec claims, locate the corresponding code
  path via the build report's pointers.
- **Build report exists but is opaque, OR no build report:** explore the
  codebase via `Glob`, `Grep`, `Read`, or `mcp__codegraph__codegraph_explore`.
  Cross-reference whatever the spec describes with current source.

For each relevant code path, capture:
- Function signature, file:line.
- What it actually does (one sentence, no fluff).
- What conditions guard the path.
- Any obvious skip — early-return, fallback, error swallow.

This is "what the code does" — independent of what the spec or any prior
verification *say* it does.

### Step A4: Three-way diff

Build a table:

| Aspect | PRD says | Code does | Smoke saw |
|---|---|---|---|
| <observable behavior> | <quote spec section> | <one-line summary + file:line> | <observed value> |

One row per behavior touching the failure. The diff makes the diagnosis
mechanical. Categories:

- **PRD ≠ code, smoke matches PRD** — code bug. Fix code.
- **PRD ≠ code, smoke matches code** — spec is stale. Recommend a `pivot`-style
  pass to update the PRD, then decide if code is actually correct.
- **PRD = code, smoke ≠ both** — environment, config, or upstream input mismatch.
  Out of scope for spec; investigate config.
- **PRD silent, code does X, smoke wants Y** — spec gap. Recommend an
  `pivot`-style pass to add the missing requirement.

If a row's "PRD says" cell is empty because the PRD has no frontmatter and the
relevant section is unclear, mark it `(PRD silent or unclear)` — that *is* the
finding. A spec that does not pin behavior cannot diagnose a smoke failure.

### Step A5: Re-run any verification against the live PRD (if available)

If a verification skill exists in the workspace (`bailiff` or equivalent) and
its prior report is stale relative to the current PRD, the verdict is no
longer evidence of anything. Suggest re-running it from scratch — but
inquest itself does not invoke it. The user decides whether to.

If the verifier was already current when smoke failed, that is the most
interesting case: the spec and code agree, the spec was verified, and the
world still broke. The diff (Step A4) will show whether the failure is in
scope of the spec at all.

Jump to **Step 6** (write the report).

---

## Mode B — Bailiff triage

Use when the trigger points at a bailiff report with open findings and asks
inquest to work them down. Fix authority in this mode is real but scoped;
smoke-mode's diagnosis-only guardrail does not apply here — B4 does.

### Step B1: Parse the bailiff report

1. Locate the bailiff report. If the user named a path, use it. Otherwise
   pick the newest `.claude/reports/<slug>-bailiff*.md` for the named slug.
2. Read the frontmatter (or infer versions from the body per plumb's
   legacy-fallback rules). Record `prd_version`, `plan_version`, and the
   current `status`.
3. **If `status: superseded`** — the report was already triaged (or amended
   away). Under REPL, `AskUserQuestion` whether to force a re-triage; under
   subagent transport, abort with the "could not diagnose — bailiff report
   already superseded by <path>" sentinel.
4. Extract findings from three sources:
   - **Static Checks table** — every row is one finding. Assign id `S<n>`.
   - **Expectation Results table** — every row with `Status: FAIL` OR
     `Status: WARN` is a finding. Assign `F<n>` for FAILs, `W<n>` for
     WARNs. Callers can scope down to FAILs only with the phrase "FAILs
     only" in the trigger.
   - **Failures section** — narrative context for each FAIL row (title,
     diagnosis phrase, actual behavior, suggested fix). Attach the phrase
     to the matching `F<n>` row.
5. If the bailiff report has no frontmatter and no parseable version signal,
   proceed but flag `retrofit_gap: true` in the eventual triage report.

### Step B2: Reload live context

For each finding queued in B1, load the surrounding truth:

1. **PRD section** — read the `§id` the finding cites (or the closest
   matching section). If the finding cites the plan, walk the plan phase to
   its referenced `§id`.
2. **Plan phase mapping** — the plan phase that owns the code path.
3. **Current source at file:line** — read the referenced file. Bailiff may
   have run against an older commit; the code at file:line now may not
   match what the report describes. That divergence is data.
4. **Prior inquest reports for this slug** — `.claude/reports/<slug>-inquest-r*.md`.
   If the same `§id` was triaged before, note the prior outcome.

### Step B3: Per-finding verify + classify

Walk the findings one at a time. For each:

1. **Verify.** Reproduce the failing behavior via one of:
   - Re-run the reproduction command the bailiff report cites (test file,
     grep pattern, etc.).
   - `Grep` for the code shape the bailiff report describes.
   - Read the source directly and cross-check against the spec.
   Trust nothing in the bailiff report until reproduced.
2. **Classify** into exactly one outcome:

   | Outcome | Meaning | Post-action |
   |---|---|---|
   | `CONFIRMED_FIXED` | Finding is real; a minimal edit within the named files removes it. | Continue to B4. |
   | `CONFIRMED_DEFERRED` | Finding is real, but the fix needs a design decision or wider changes than a triage should take on. | Record; no edit. |
   | `REJECTED_NOT_REAL` | Bailiff's claim does not reproduce — false positive (or already fixed by hand between bailiff runs). | Record evidence; no edit. |
   | `REJECTED_SPEC` | The code matches what the plan actually says; bailiff was measuring against a mis-stated spec. | Record; recommend `run pivot for §<id>`. |
   | `REJECTED_ENVIRONMENT` | Behavior differs only in a specific config/runtime; code is correct against every environment the spec pins. | Record; recommend env investigation. |

3. **Guardrails during classification** (mechanical, no judgment calls):
   - Finding scope is **package or directory** (no file:line, no single
     function name) → automatically `CONFIRMED_DEFERRED` with evidence
     line `finding scope is package-level, not triage-safe` (D2).
   - Fix would touch **>3 files**, require a new dependency, or force an
     interface change → automatically `CONFIRMED_DEFERRED`.
   - Finding lacks any file:line, has no reproducible command, and no
     grep target → `CONFIRMED_DEFERRED` with `evidence: unlocatable`.
   - Code at the cited file:line no longer matches bailiff's description
     as of the current commit sha → `REJECTED_NOT_REAL` with the sha
     recorded (disambiguates false-positive from between-run hand fix).

### Step B4: Apply fixes

**Only for `CONFIRMED_FIXED`.** This is the only place inquest writes code.

1. Edit within the finding's named files/functions only. **No drive-by
   reformatting, no adjacent cleanups, no "while I'm here" edits.**
2. Re-verify locally:
   - Re-run the same check that produced the finding (grep pattern, single
     named test file), OR
   - Read the resulting diff and confirm the reported code shape is gone.
3. **Do not run the project's full test suite** (`go test ./...` or
   equivalent). That is bailiff's job; the next step tells the caller to
   re-run bailiff.
4. If re-verification fails — the edit was made but the finding did not
   close — downgrade this row to `CONFIRMED_DEFERRED` and record both the
   attempted diff and why it didn't close.

### Step B5: Flip the bailiff report status

Metadata only. **Never touch the bailiff report body.**

Choose the status transition from B3's aggregate outcomes:

| Triage outcome | New `status` | Sidecar fields written |
|---|---|---|
| Any `CONFIRMED_FIXED` present | `superseded` | `superseded_by: <this inquest report>`, `triage_outcome: fixed`, `triaged_at: <today>`, `findings_status: {...}` |
| Any `CONFIRMED_FIXED` AND any `CONFIRMED_DEFERRED` | `superseded` | as above, plus `triage_outcome: partial`, `findings_status: {...}` |
| All findings `REJECTED_*` (nothing fixed, nothing deferred) | `current` (unchanged) | `triaged_by: <this inquest report>`, `triage_outcome: clean`, `triaged_at: <today>`, `findings_status: {...}` |
| Any `CONFIRMED_DEFERRED` present but zero fixes | `current` (unchanged) | `triaged_by: <this inquest report>`, `triage_outcome: deferred`, `triaged_at: <today>`, `findings_status: {...}` |

#### The `findings_status:` map (main-agent read surface)

After the sidecar block, emit a `findings_status:` YAML map into the
bailiff frontmatter. This is what a main agent running under subagent
transport reads to decide per-finding routing without opening any
markdown body.

**Shape.** One entry per bailiff finding id — `F<n>` for FAILs,
`W<n>` for WARNs, `S<n>` for Static Checks. Values are exact strings
from B3: `CONFIRMED_FIXED`, `CONFIRMED_DEFERRED`, `REJECTED_NOT_REAL`,
`REJECTED_SPEC`, `REJECTED_ENVIRONMENT`. Ordering follows bailiff's
original report order.

```yaml
findings_status:
  F1: CONFIRMED_FIXED
  F2: REJECTED_NOT_REAL
  W1: CONFIRMED_DEFERRED
  S1: CONFIRMED_FIXED
```

**Re-triage merge rules.** If the bailiff frontmatter already carries
a `findings_status:` map (a prior triage run wrote it), merge — do not
overwrite:

- **Existing keys' values may change** (e.g. a `CONFIRMED_DEFERRED`
  from the first run becomes `CONFIRMED_FIXED` in the second).
- **New keys added** if the second pass classified findings the first
  did not (rare — usually implies bailiff was re-parsed at a later
  version).
- **Never delete keys.** A `CONFIRMED_FIXED` from run 1 that run 2
  doesn't re-touch stays `CONFIRMED_FIXED`. The map's semantics are
  "current triage outcome per finding," not history. History lives in
  the stacked `-r<N>.md` reports.

Read the existing bailiff frontmatter before writing; if a
`findings_status:` block is present, merge in memory and re-emit the
whole block. Never write two `findings_status:` keys into the same
frontmatter.

If the bailiff report has no frontmatter:

- **Under REPL** — `AskUserQuestion` to offer retrofit (same idiom as
  pivot Step 4). If the user accepts, the retrofit block MUST include
  the `findings_status:` map — retrofit is preferred over the
  notice-only fallback for exactly this reason. If the user declines,
  prepend a `> **Triaged by <inquest-path> on <today>** — see triage
  report for outcome.` notice near the top of the body; set
  `retrofit_gap: true` in the triage report and DO NOT write the map
  (there is no frontmatter to hold it).
- **Under subagent transport** — retrofit is not available (no user to
  ask). Prepend the `> **Triaged by …**` notice unconditionally, set
  `retrofit_gap: true` in the triage report, and skip the
  `findings_status:` map. The main agent that receives the return line
  will see `retrofit_gap: true` in the triage report and know per-finding
  state is only available by reading the inquest report body.

Jump to **Step 6**.

---

### Step 6: Write the report

Both modes rejoin here. Pick the template by mode:

- **Smoke mode** → `references/inquest-report-template.md`
- **Triage mode** → `references/inquest-triage-template.md`

Write to `.claude/reports/<slug>-inquest-r<N>.md` (or `claude/reports/...`
if the project doesn't use the dot prefix). `<N>` is the next integer for
this feature — never overwrite a prior inquest report; smoke and triage
runs both stack.

Both reports carry:

- Frontmatter with the versions you could pin down — frontmatter values when
  available, inferred values (with `~`) otherwise, `unknown` if neither.
  Triage adds `bailiff_input:` and `bailiff_version:` to pin the exact
  artifact under triage.
- A per-mode body — three-way diff + diagnosis (smoke) or findings table +
  fixes + rejections (triage).
- A `Suggested next step` that the caller can act on as-is.

Suggested next steps by mode:

- **Smoke:** "Fix code at <file:line>", "Update the PRD — missing the case
  we hit (run `pivot`)", "Investigate <config/env>; spec is fine", "Re-run
  verification after PRD update".
- **Triage:** "re-run bailiff" (fixes landed), "run pivot for §<id>"
  (REJECTED_SPEC), "investigate <env>" (REJECTED_ENVIRONMENT), or "none"
  (all clean).

### Step 7: Tell the user / caller

**Under REPL** — a two-sentence summary. The report has the detail; the
chat reply states the diagnosis (smoke) or the triage counts + next step
(triage). Do not narrate the workflow — state the answer.

**Under subagent transport** — a single line, per the [Subagent
transport](#subagent-transport) return contract. No preamble, no summary,
no reasoning.

### Step 8: Update the context ledger

If `.claude/memory/context-ledger.md` exists (or you can create it), update
the `## Inquest` section:

1. Read the current ledger.
2. If the Inquest section already has content, append the old content to
   `.claude/memory/history/ledger-archive.md` with an
   `## Entry: inquest @ {timestamp}` header.
3. Overwrite the Inquest section with:
   - For triage runs: `- **{slug}** ({date}, {commit}): triage — fixed={F} rejected={R} deferred={D} → {next step}`
   - For smoke runs: `- **{slug}** ({date}, {commit}): smoke — {diagnosis} → {next step}`
   - Keep last 3 entries maximum — drop the oldest if adding a 4th.
4. Update the `Last updated:` header line.
5. Keep the section within 10 content lines.

See [charter/references/context-ledger-spec.md](../charter/references/context-ledger-spec.md)
for the full ledger protocol.

## What this skill does NOT do

- **Smoke mode does not write code fixes.** Diagnosis only.
- **Triage mode writes code only for `CONFIRMED_FIXED` findings**, and only
  within files/functions the finding names. No drive-by refactors, no
  adjacent cleanups, no interface changes. If a real fix would need wider
  changes, the outcome downgrades to `CONFIRMED_DEFERRED`.
- Does not run any other skill automatically. The user decides whether to
  pivot the spec, re-run verification, or fix code. Inquest recommends;
  the user (or another skill) executes. Triage mode explicitly does NOT
  invoke `bailiff` after fixes land, does NOT invoke `pivot` for
  `REJECTED_SPEC` outcomes, and does NOT run the project's full test suite
  after fixes.
- Does not modify the PRD or plan. The smoke/triage report is a *finding*,
  not an authoritative spec change.
- Does not rewrite the bailiff report body. Triage flips `status` and
  writes sidecar fields only — the body is preserved as evidence of what
  bailiff saw.
- Does not require any companion skill to be installed. It works alone with
  whatever artifacts exist in the workspace.

## Guidelines

- **Evidence over intuition.** Every row in the three-way diff (smoke) or
  Findings table (triage) must cite file:line for "code does" and a §id
  (or quote) for "PRD says." If you can't cite, mark it as PRD-silent or
  code-untraceable — that *is* the finding.
- **Drift first when you can detect it.** If `plumb` (or any drift-detection
  tool) is available and shows STALE artifacts, surface that before debugging. Half the "smoke
  broke our feature" reports trace to a PRD that moved without the code or
  verifier catching up. If no such tool is available, do the same comparison
  manually — it's just slower.
- **Stack reports.** Inquest reports accumulate. `<slug>-inquest-r1.md`,
  `<slug>-inquest-r2.md`, etc. — never overwrite. The history of what
  failed or was triaged is part of the spec's lineage.
- **One incident per report.** If the user reports two unrelated failures
  in one message, write two reports. Same rule for triage: one bailiff
  report per triage run.
- **Triage: finding-scoped fixes only.** In Mode B, code edits are
  restricted to files/functions the finding pointers name. Anything wider
  is `CONFIRMED_DEFERRED`, not "let me just tidy this up." The guardrail
  is mechanical; there are no exceptions.
- **Triage: local re-verify only.** After a fix, verify with the same
  check that produced the finding — grep, single named test file, source
  diff read. Do not run the project's whole test suite; that is bailiff's
  job. The return line names "re-run bailiff" as the next step when fixes
  landed.
- **Triage: status flip is metadata, not body.** The bailiff report's body
  records what bailiff saw at run time; it stays intact even when
  superseded. Only frontmatter (or a `> Triaged by …` notice, if no
  frontmatter) changes.
- **Triage: the `findings_status:` map is the main-agent read
  surface.** A main agent running under subagent transport should read
  the bailiff frontmatter's `findings_status:` map to decide per-finding
  routing — it's YAML-parseable, constant-cost, and drilldown to
  evidence is one file-open away via `superseded_by`. Reading the
  triage report body is only necessary when the main agent needs a
  specific finding's diff summary, rejection evidence, or the
  Unknowns block. If `retrofit_gap: true` is set in the triage report,
  the map is unavailable — fall back to the triage report body.
- **Standalone.** This skill works alone, without `bailiff`, `pivot`, or
  `plumb`. Recommendations may reference those skills, but they are
  always optional — the user can do the equivalent by hand.
