---
name: scout
description: Detect codebase drift since the last warmup or scout run. Compares git history, Go sources, and dependencies against stored conventions and rules to flag structural changes, convention deviations, dependency shifts, and interface modifications. Writes drift reports to .claude/memory/history/drift/ and bootstraps .claude/memory/current.md on first run. Never modifies rules or analyses — convention updates require user approval via charter. Use this skill when the codebase has evolved and you suspect the AI's understanding is stale, or after a batch of changes lands on the main branch.
allowed-tools: Read, Write, Bash, Grep, Glob, Agent
---

Detect how a Go codebase has drifted since the last warmup snapshot. Scout compares the current state of the repo against stored conventions and produces a structured drift report — flagging what changed, what diverged from conventions, and what needs user decision before updating memory.

Scout never modifies `.claude/rules/` or `.claude/analyses/`. Convention and rule updates require user approval and are applied by the companion skill **charter**. Scout **does** write to `.claude/memory/` in two cases:

1. **Bootstrap** — on first run, scout creates `.claude/memory/current.md` and the `history/drift/` directory structure
2. **Drift reports** — each scan appends a new report under `.claude/memory/history/drift/`

These are append-only outputs. Scout never edits or deletes existing memory files.

---

## Prerequisites

Scout reads the following warmup outputs as its baseline:

- `.claude/rules/{project}-dev-conventions.mdc` — the convention spec (source of truth)
- `.claude/analyses/conventions.md` — detailed conventions with code examples

If any of these are missing, scout will tell the user to run warmup first and exit.

Scout also reads `.claude/memory/current.md` for the last-known commit hash. If this file does not exist (first run), scout bootstraps it — see Phase 0.

---

## Output

- **Drift report:** `.claude/memory/history/drift/{branch}-{hash}-{timestamp}.md`
  - `{branch}` = current branch name (e.g., `main`)
  - `{hash}` = first 7 chars of HEAD commit hash
  - `{timestamp}` = ISO format `YYYYMMDDTHHNN`
  - Example: `main-a3f2c1d-20260403T1430.md`

---

## Workflow

### Phase 0 — Prerequisites & Git Anchor

Validate prerequisites and establish the baseline commit for comparison.

**Step 1: Check warmup outputs exist.**

Look for these files (glob for the `.mdc` since the project name varies):

- `.claude/rules/*-dev-conventions.mdc`
- `.claude/analyses/conventions.md`

If either is missing → tell the user: "Run warmup first to establish a baseline." Exit.

**Step 2: Get current git state.**

1. Run `git rev-parse --abbrev-ref HEAD` → current branch
2. Run `git rev-parse --short=7 HEAD` → current commit hash
3. Run `git rev-parse HEAD` → full commit hash (for git diff)

**Step 3: Check or bootstrap `.claude/memory/current.md`.**

If `.claude/memory/current.md` does not exist — this is the first scout run. Bootstrap:

1. Create `.claude/memory/` directory structure:
   ```
   .claude/memory/
   ├── current.md
   └── history/
       └── drift/
   ```
2. Write `.claude/memory/current.md` with the current state:
   ```markdown
   # Scout Baseline
   
   **Branch:** {branch}
   **Commit:** {hash}
   **Full hash:** {full-hash}
   **Date:** {timestamp}
   
   Bootstrapped from warmup outputs. This is the starting point for future drift detection.
   ```
3. Report to user: "Baseline created at commit {hash}. Run scout again after new changes land."
4. Exit. (No drift to detect on first run — we just set the anchor.)

If `.claude/memory/current.md` exists — read the stored commit hash from it.

**Step 4: Compare hashes.**

- If stored hash equals current HEAD → "No changes since last scan at {hash}." Exit.
- Otherwise → proceed to Phase 1 with old hash (from `current.md`) and new hash (current HEAD).
- Build the report filename: `{branch}-{hash}-{timestamp}.md`

### Phase 1 — Structural Drift

Detect changes to the repo's package layout and file organization.

Run `scripts/go/detect_structural.js` with the old and new commit hashes:

```bash
node scripts/go/detect_structural.js <old-hash> <new-hash>
```

This uses `git diff --name-status` to identify:
- New Go packages (directories with new `.go` files)
- Removed packages
- Renamed/moved files
- Significant file additions or deletions within existing packages

Output: JSON lines to stdout, one per structural change.

Read [references/drift-spec.md](./references/drift-spec.md) for the full output schema.

### Phase 1.5 — Read Context Ledger

Before analyzing convention drift, check if changes were planned.

If `.claude/memory/context-ledger.md` exists, read the **Blueprint** section. If a drift finding in Phase 2 matches a blueprint decision (e.g., blueprint decided to switch from `errors.Wrap` to `fmt.Errorf`), annotate that finding in the report as `[PLANNED]` instead of `[DECIDE]`. Planned changes are intentional evolution, not drift — they don't need user review.

If the ledger doesn't exist, skip this step and treat all drift as unplanned.

Scout does not write to the ledger. See [charter/references/context-ledger-spec.md](../charter/references/context-ledger-spec.md) for the full ledger protocol.

### Phase 2 — Convention Drift

Detect deviations from stored coding conventions in changed files.

Run `scripts/go/detect_conventions.js` with the rules file and changed file list:

```bash
node scripts/go/detect_conventions.js <rules-file> <file1.go> <file2.go> ...
```

This parses each changed Go file and checks against the convention spec for:
- Error handling patterns
- Logging patterns
- Context propagation
- Defer/cleanup usage
- Type definition conventions
- Naming conventions

Output: JSON lines to stdout, one per convention deviation.

### Phase 3 — Dependency Drift

Detect changes to project dependencies.

Run `scripts/go/detect_dependencies.js` with the old and new commit hashes:

```bash
node scripts/go/detect_dependencies.js <old-hash> <new-hash>
```

This diffs `go.mod` between commits to identify:
- New dependencies
- Removed dependencies
- Version bumps (major / minor / patch)

Output: JSON lines to stdout, one per dependency change.

### Phase 4 — Interface Drift

Detect changes to exported symbols in modified packages.

Run `scripts/go/detect_interfaces.js` with the old hash, new hash, and changed Go files:

```bash
node scripts/go/detect_interfaces.js <old-hash> <new-hash> <file1.go> <file2.go> ...
```

This compares exported functions, types, and interfaces between the two commits:
- New exports
- Removed exports
- Signature changes

Output: JSON lines to stdout, one per interface change.

### Phase 5 — Severity Assessment & Report

Combine all detection outputs and produce the drift report.

Run `scripts/go/severity_filter.js` piping in the combined JSON output:

```bash
cat structural.json conventions.json dependencies.json interfaces.json | node scripts/go/severity_filter.js
```

This:
1. Merges all findings
2. Assigns overall severity: **minor** / **moderate** / **significant**
3. Tags convention deviations that need user decision:
   - `[DECIDE]` — drift is significant enough to warrant a convention update or smell flag
4. Generates the markdown report

Write the report to `.claude/memory/history/drift/{branch}-{hash}-{timestamp}.md`.

### Phase 6 — User Review Gate

Present the report summary to the user. For each `[DECIDE]` item, ask:

- **Update convention** — this is an intentional evolution. Charter should update the rules.
- **Flag as smell** — this is accidental divergence. Leave conventions unchanged.

Tag the user's decisions in the report as `[UPDATE]` or `[SMELL]` respectively.

The report is now ready for charter to consume. Do not modify any other files.

---

## Ground Rules

- **Git-diff only** — never scan the entire repo. Only analyze files that changed between commits.
- **Rules are the spec** — convention drift is measured against the `.mdc` rules file, not general best practices.
- **Report, don't fix** — scout detects and reports. It never modifies code, rules, or convention files. Writes are limited to `.claude/memory/` (baseline + drift reports).
- **User decides on drift** — when conventions and code diverge significantly, the user decides which is right.
- **Commit-anchored** — every report is tied to a specific commit hash for reproducibility.
- **Speed matters** — run detection scripts in parallel when phases are independent (1-4 can overlap).
- **Track progress** — use task management tools to give the user visibility into each phase.
