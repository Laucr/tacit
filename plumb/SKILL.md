---
name: plumb
description: Check whether each feature's plan, build report, and bailiff verdict are still true to the live PRD. Reads the YAML frontmatter (or infers versions from legacy artifacts) and prints a per-feature alignment table — STALE means a plan or verdict no longer matches the spec it claims to implement. Use this skill when the user asks "is anything stale?", "what's drifted?", "is the plan still in sync with the PRD?", "did the bailiff verify the current spec?", or before kicking off a builder/bailiff run on a feature that has been edited. Standalone — works on any markdown PRD/plan/report layout, with or without frontmatter.
---

# Plumb

The carpenter's plumb line, but for specs. Pointed at a project's
`.claude/{prds,plans,reports}/` (or `claude/{...}` as a fallback), it answers
in one command: is each plan still true to the PRD it claims to implement? Is
each build report still true to the plan it followed? Is each verdict still
evidence about the current spec?

This skill is **standalone**: it does not require you to be using `blueprint`,
`builder`, `bailiff`, or `pivot`. It just reads markdown artifacts and reports
on what they claim about each other. If you have a different workflow that
produces `.claude/prds/`-style files (or just plan files in any directory),
plumb still works on them.

It is also **legacy-tolerant**: artifacts without YAML frontmatter are not
errors. Plumb infers what it can from `**Version:**` lines in the body,
filename suffixes (`foo_v1.3.md`), and `**PRD version:**` references — fields
inferred this way are marked with `~` (e.g. `v3.7~`). Comparisons that hinge on
inferred fields produce `WARN`, never `STALE` — the user shouldn't be told the
plan is stale because we guessed the version off a filename.

## When to use

- User asks: "is anything stale", "what's drifted", "is the plan in sync"
- Before manually rebuilding or re-verifying a feature whose PRD has been edited
- After applying a pivot (e.g. via `pivot`) to confirm downstream artifacts
  were marked correctly
- Periodically, to catch features where the PRD edited silently

The skill is read-only and side-effect-free. Running it never breaks anything.

## Output Location

Plumb is read-only — it prints a table to stdout and does not write any
file under `.claude/`. The optional `--report` flag dumps the same table to
`.claude/reports/<feature>-drift.md` for sharing.

## Frontmatter (canonical, optional)

When new artifacts are written by `blueprint` / `builder` / `bailiff`, they
carry YAML frontmatter:

```yaml
---
feature: <slug>
artifact: prd | plan | build | bailiff
version: <semver-ish: 1.0, 1.1, 2.0, ...>
prd_version: <plan/build/bailiff: which PRD version this aligns to>
plan_version: <build/bailiff only: which plan version this aligns to>
last_aligned: <YYYY-MM-DD>
status: current | stale | superseded
---
```

This is the precise, no-guessing form. If you adopt it for new artifacts you
get crisp `STALE` verdicts; if you don't, plumb falls back to inference
and produces softer `WARN` / `UNKNOWN` signals.

## Legacy fallback rules

When frontmatter is absent or partial, plumb tries (in order):

1. `**Version:** N.M` line in the body (also matches bold/blockquote/no-bold).
2. `_v1.3` / `-v1.3` suffix in the filename stem.
3. `**PRD version:** N.M` and `**Plan version:** N.M` for cross-references.
4. `**Date:** YYYY-MM-DD` for `last_aligned`.
5. Filename stem (with `-build`, `-bailiff`, `-r<N>`, `_v<N>`, `_prd`, `_plan`
   suffixes stripped) for `feature`.

Anything still missing renders as `v?` or `—`. The corresponding row is
classified `LEGACY` (no version on either side) or `UNKNOWN` (one side
missing); neither counts toward `--strict` exit code 1.

## What "drift" means

For each feature, plumb compares versions:

| Comparison | Drift if | Severity |
|---|---|---|
| `plan.prd_version` vs `prd.version` | plan behind | STALE (or WARN if inferred) |
| `build.prd_version` vs `prd.version` | build behind | STALE (or WARN if inferred) |
| `build.plan_version` vs `plan.version` | build behind | STALE |
| `bailiff.prd_version` vs `prd.version` | bailiff behind | STALE — verdict invalid |
| `bailiff.plan_version` vs `plan.version` | bailiff behind | WARN |
| plan claims **newer** `prd_version` than the PRD itself | — | WARN (PRD bump forgotten?) |
| both sides have no version anywhere | — | LEGACY |
| one side has a version, the other doesn't | — | UNKNOWN |
| any `status: superseded` | — | excluded from comparison |

Versions compare as semver-ish (`major.minor`); a major bump on the PRD flags
every downstream artifact as stale until each is bumped to match.

## Workflow

1. Walk `.claude/{prds,plans,reports}` (or `claude/{prds,plans,reports}` as
   fallback) under the working directory.
2. For each markdown file: parse YAML frontmatter; if missing, run inference.
3. Group by `feature`; pick the highest-version artifact per kind as canonical.
4. Compute drift per the table above.
5. Print the table. Exit 0 unless `--strict` and at least one `STALE` was found.

## Running

```bash
python scripts/drift_check.py                         # all features
python scripts/drift_check.py --feature emb-search    # one feature (substring)
python scripts/drift_check.py --strict                # exit 1 on STALE
python scripts/drift_check.py --legacy-quiet          # hide UNKNOWN/LEGACY-only features
python scripts/drift_check.py --report                # write .claude/reports/<feature>-drift.md
python scripts/drift_check.py --root /path/to/project # explicit project root
```

The script is stdlib-only Python (no PyYAML); the frontmatter parser mirrors
`herald/scripts/render.py:split_yaml_frontmatter` for consistency.

## Reading the output

```
multi-modal-emb-search-hive-sink:
  prd       v3.7      2026-06-26   current
  plan      v2.1      2026-06-23   STALE   prd 1 major rev ahead
  build     v3.7      2026-06-26   current
  bailiff   v3.3      2026-04-08   STALE   prd 4 minor revs ahead — verdict invalid
```

- `v3.7~` (with `~`) — version was inferred from the body or filename, not
  declared in frontmatter. Treat as "best-effort."
- `v?` — no version found anywhere.
- `—` — artifact does not exist.
- `legacy` — no version on either side; not actionable.
- `UNKNOWN` — one side has a version, the other doesn't; can't compare.
- `WARN` — comparison was made but rests on inferred data, OR the plan claims
  a newer PRD version than the PRD itself (forgot to bump?).
- `STALE` — confident drift; needs attention.

## What to do with drift

Plumb itself never modifies files. It is a sensor, not an actuator.
When it surfaces drift, the response depends on what's stale:

- **Plan is STALE / WARN** — the requirements moved. Either edit the plan in
  place (bumping its `version` and syncing `prd_version`) or run a pivot skill
  like `pivot` if you have one. If you just author plans by hand, the message
  is "go re-read the PRD and update the plan."
- **Build is STALE** — the implementation was made against an older spec.
  Re-build, or accept it consciously and bump the build report's `prd_version`
  to acknowledge the delta.
- **Bailiff is STALE** — the verdict no longer applies to the current spec.
  Re-run bailiff; the old verdict file should be marked `status: superseded`.
- **LEGACY everywhere** — your repo predates the frontmatter convention.
  Either retrofit a few key artifacts by hand (one frontmatter block per file)
  or use `--legacy-quiet` to focus on actionable signals.

## Guidelines

- **Read-only.** Plumb never modifies a file. Mutations are the user's
  job (or another skill's).
- **Tolerate everything.** Missing frontmatter, partial frontmatter, hand-edited
  artifacts, foreign repos that use `claude/` instead of `.claude/` — none of
  it should produce an error or a panic.
- **Inferred fields are softer.** A `STALE` verdict requires both sides to
  have explicit (not inferred) versions. Otherwise it's `WARN`.
- **Don't auto-fix.** Surfacing drift is the whole point. Auto-fixing hides it.
- **Standalone.** This skill does not call out to any other skill or tool. If
  you're using it without `blueprint` / `builder` / `bailiff`, that's fine —
  it just reads files and reports.
