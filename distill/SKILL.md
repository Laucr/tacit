---
name: distill
description: Periodic meta-review of every bailiff report on disk. Scans doc-root folders for `*bailiff*.md` files, abstracts the caught problems into named recurring failure modes with guardrails, and saves the digest as a dated `bailiff-lessons-YYYY-MM-DD.md`. Use this skill when the user asks to "distill bailiff findings", "review bailiff reports", "roll up bailiff lessons", "abstract bailiff patterns", "do the periodic bailiff meta-review", or wants to make individual bailiff findings actionable across projects.
---

# Distill

A cross-repo, point-in-time digest of every bailiff report the user has on disk. The goal is to convert individual "this build had bug X" findings into named, reusable failure-mode categories with guardrails, so the next feature avoids the same trap.

This is a **meta-review**. It reads only bailiff reports — never the audited code itself. The point is pattern extraction, not re-verification.

Docs produced by this skill are cumulative. Each run is a new file dated to that day; the diff between runs is where the value lives (which reports were added, which categories recurred, which retired).

---

## Inputs and Defaults

- **Doc roots (input):** One or more folders. Each root contains repo-shaped subfolders with bailiff reports at `<repo>/claude/reports/*bailiff*.md`.
  - Default: `/root/.ai/` (contains `edu_service/`, `mas-edu-strategy/`, `data_streaming_hive_spark3/`, `mas-tool/`, etc.).
- **Output folder:** where the digest is written.
  - Default: `/root/.ai/harness/`.
- **Output format reference:** `references/output-format.md` — the format spec every digest must follow. Match its section order, header wording, and sources-list format when in doubt.

The skill is idempotent: running twice on the same day overwrites the same file rather than appending.

## Steps

### 1. Discover bailiff reports

Glob every doc root with `<root>/*/claude/reports/*bailiff*.md`. Do NOT descend into subdirs beyond that pattern — bailiffs live at exactly that depth by convention (`repo/claude/reports/`).

If a root doesn't match anything, note it in the output but don't error out.

### 2. Read each report and extract

For each file, capture:

- **Path** (relative to the doc root, e.g. `edu_service/claude/reports/oss-dedup-bailiff.md`).
- **Report date** — usually a `**Date:**` line in the body; if absent, fall back to the file mtime and mark it as inferred.
- **Frontmatter versions** — `prd_version`, `plan_version`, `status` (e.g. `stale`, `stale_since`) if present.
- **Verdict** — `PASS` / `FAIL` / `PARTIAL` / `RESOLVED` etc.
- **Failure sections** — usually headers like `## Failures`, `### F1`, `## Warnings`.
- **Resolution** — if the report was later fixed, note whether resolution is documented in the same file.

### 3. Abstract into named failure modes

Group similar findings across reports into named categories. Each category must have three parts, in this order:

- **What happened.** One concrete example, citing the bailiff file by path and (if possible) the exact identifier/line. If the same failure mode appeared in multiple reports, list each one.
- **Why it slipped past compile / CI / earlier review.** The "how did this reach the bailiff at all?" analysis. This is what makes the guardrail non-obvious.
- **Guardrail.** Concrete, actionable prevention — checklist items, grep patterns, plan-phase requirements, or bailiff-template additions. Not "be careful"; something a future skill or plan can mechanically enforce.

Prefer generalizing over cataloguing. Two very similar findings under one name is better than two nearly-identical categories. Do not add categories with only speculation — every category must trace to at least one concrete bailiff finding.

**Performance findings track separately.** The `bailiff` skill carries a numbered performance-pitfall catalogue at `<bailiff-skill-path>/references/perf-pitfalls.md`. If a bailiff report cites `perf-pitfall #N` in its failure titles or notes, group those findings under the pitfall's existing number rather than inventing a new category — cross-feature recurrence of the same pitfall is the signal to strengthen the shared guardrail, not to rename it. In the digest, keep the pitfall number in the category heading (e.g. "perf-pitfall #3 recurred: sub-batch / semaphore / yaml-batch misalignment").

### 4. Add cross-cutting lessons

After the numbered categories, add a "Cross-cutting bailiff-workflow lessons" section for meta-observations that apply regardless of specific bug. Examples of things that belong here:

- `go build` / `mvn` is the floor, not the ceiling — bailiff catches contract violations, and contracts live in the PRD.
- Static inspection is a coverage gap, not a verification — mark `SKIP`, not `PASS`.
- Bailiff checklists are cumulative — every failure mode found should get folded into a template so the next run doesn't rediscover it.
- Copy-paste from sibling templates is a top failure source.
- Bailiffs are version-pinned — trust the `prd_version` frontmatter.

The specific list should reflect what actually shows up in the corpus, not boilerplate.

### 5. Save the digest

Write to `<output>/bailiff-lessons-YYYY-MM-DD.md`, using today's date. See `references/output-format.md` for the full shape spec.

Overwrite if the target file already exists — this is idempotent on a per-day basis.

### 6. Report back

Print a one-line summary to the user:

> Wrote `<path>`. N failure modes across M source reports (dated <earliest>..<latest>).

If any bailiff files were unreadable or their dates couldn't be extracted, list them.

## What NOT to do

- Do **not** open or read the audited source code. This skill only reads bailiff reports.
- Do **not** edit existing bailiff reports. If one is stale (per its own frontmatter), note it in the output — resolving staleness is the `pivot` / `plumb` skill's job.
- Do **not** produce a per-repo digest — the value is in cross-repo pattern extraction. One digest per run, spanning all doc roots.
- Do **not** add categories with only speculation. Every category must trace to at least one concrete bailiff finding.
