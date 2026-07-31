---
name: charter
description: Apply approved drift updates to project memory and conventions. Reads scout drift reports with user-tagged decisions ([UPDATE] or [SMELL]), updates .claude/memory/current.md and .claude/rules/, and compacts history when it grows too large. Charter is the only skill that modifies stored conventions — it requires a reviewed scout report as input. Use this skill after scout has produced a drift report and the user has approved which changes to accept.
allowed-tools: Read, Write, Bash, Grep, Glob, Agent
---

Apply approved drift to project memory. Charter reads a scout drift report where the user has tagged each decision as `[UPDATE]` (accept the drift as a new convention) or `[SMELL]` (reject it, leave conventions unchanged), then updates the stored memory and convention files accordingly.

Charter is the **only skill** that modifies `.claude/memory/current.md`, `.claude/rules/`, and `.claude/analyses/`. This is intentional — all convention changes flow through charter after explicit user approval.

---

## Inputs

Charter requires:

1. **A reviewed scout drift report** — a file under `.claude/memory/history/drift/` with `[UPDATE]` and `[SMELL]` tags on all `[DECIDE]` items. If any `[DECIDE]` items remain unresolved, charter will refuse to proceed and ask the user to finish reviewing.

2. **Current memory files** (to update):
   - `.claude/memory/current.md` — state snapshot (commit hash, structure summary)
   - `.claude/rules/{project}-dev-conventions.mdc` — convention spec
   - `.claude/analyses/conventions.md` — detailed conventions with examples

---

## Outputs

Charter modifies these files in place:

| File | What changes |
|------|-------------|
| `.claude/memory/current.md` | Commit hash advanced to the report's commit. Structural summary updated. |
| `.claude/rules/*-dev-conventions.mdc` | Convention rules updated for `[UPDATE]` items. `[SMELL]` items noted in a smell log but conventions left unchanged. |
| `.claude/analyses/conventions.md` | Detailed convention examples updated/added for `[UPDATE]` items. |

Charter also:
- Marks the processed drift report as applied (adds `**Status:** APPLIED` header)
- Compacts history if the `history/drift/` directory exceeds the threshold (see Phase 3)

---

## Workflow

### Phase 0 — Validate Prerequisites & Input

**Step 0: Verify scout skill exists.**

Charter cannot run standalone — it depends on scout's output. Check that the scout skill is installed:

1. Look for `scout/SKILL.md` in the skills directory (peer to `charter/`)
2. If not found → tell the user: "Charter requires the scout skill. Install scout first." Exit.

**Step 1: Verify scout has produced output.**

Check that the memory structure exists:

1. Check `.claude/memory/` directory exists
2. Check `.claude/memory/history/drift/` directory exists
3. If either is missing → "No scout output found. Run scout first to detect drift." Exit.

**Step 2: Locate the drift report.**

The user will reference a specific report, or charter should find the most recent unprocessed report:

1. If user provides a path → use it
2. Otherwise → scan `.claude/memory/history/drift/` for reports without `**Status:** APPLIED` (exclude `_compacted-*.md` files)
3. Pick the most recent unapplied report (by timestamp in filename)
4. If no unapplied reports exist → "No pending drift reports. Run scout first." Exit.

**Step 3: Check all decisions are resolved.**

Parse the report's "Recommendations for Charter" section. Run `scripts/parse_report.js`:

```bash
node scripts/parse_report.js <report-file>
```

This outputs JSON with:
- `updates` — items tagged `[UPDATE]` (to apply)
- `smells` — items tagged `[SMELL]` (to log but skip)
- `undecided` — items still tagged `[DECIDE]` (block proceeding)

If `undecided` is non-empty → tell the user which items need decisions. Exit.

**Step 4: Present the update plan.**

Show the user a summary of what will change:

```
Charter will apply the following updates:
- Update structural map: new package pkg/newfeature
- Update convention: error handling → fmt.Errorf with %w (was errors.Wrap)
- Update dependency list: +github.com/newlib/v2

The following were flagged as smells (no convention change):
- Ignored error in pkg/api/handler.go:42

Proceed? [Y/N]
```

Wait for user confirmation before modifying any files.

### Phase 1 — Update Memory

Apply the approved changes. For each `[UPDATE]` item, update the appropriate file.

**Step 1: Advance the commit anchor.**

Read `.claude/memory/current.md` and update:
- `**Commit:**` → new commit hash from the report
- `**Full hash:**` → new full hash
- `**Date:**` → report date
- `**Branch:**` → report branch

**Step 2: Update structural map.**

For structural changes tagged `[UPDATE]`:
- New packages → add to the "Where to Work" section of the `.mdc` rules file
- Removed packages → remove from the rules file
- Add a brief description based on the drift report

**Step 3: Update conventions.**

For convention changes tagged `[UPDATE]`:
- Update the matching convention in `.claude/rules/*-dev-conventions.mdc`
- Update the detailed example in `.claude/analyses/conventions.md`
- Preserve the prescriptive style: "always do X" with a code example

**Step 4: Update dependency notes.**

For dependency changes:
- New deps → note in conventions if they affect coding patterns (e.g., new logger library)
- Removed deps → remove references from conventions if present
- Version bumps → update version references if any exist in conventions

**Step 5: Update interface map.**

For interface changes tagged `[UPDATE]`:
- New exports → add to structure documentation if they represent significant API surface
- Removed exports → note the removal
- Signature changes → update any convention examples that reference the old signature

### Phase 2 — Log Smells

For items tagged `[SMELL]`:

1. Append to `.claude/memory/current.md` in a "Known Smells" section:
   ```markdown
   ## Known Smells
   
   | Date | Commit | Type | File | Description |
   |------|--------|------|------|-------------|
   | 2026-04-03 | a3f2c1d | error_handling | pkg/api/handler.go:42 | Uses fmt.Errorf but convention says errors.Wrap |
   ```

2. If the same smell appears in 3+ consecutive reports, escalate: notify the user that this pattern may actually be an intentional convention shift, and suggest reconsidering.

### Phase 3 — Compact History & Ledger Archive

After applying updates, check if history compaction is needed.

**Drift history compaction:**

Run `scripts/compact_history.js`:

```bash
node scripts/compact_history.js .claude/memory/history/drift/
```

**Compaction rules:**
- **Trigger:** more than 10 drift reports in `history/drift/`
- **Action:** summarize the oldest 80% into a single `_compacted-{date}.md` file
- **Preserve:** keep the newest 20% as individual reports
- **Summary format:** one-line-per-report with date, commit, severity, and key changes

**`current.md` size cap:**
- If `current.md` exceeds 200 lines, trim the "Known Smells" table to the most recent 20 entries
- Archive older smells to `.claude/memory/history/smells-archive.md`

**Ledger archive compaction:**

Check `.claude/memory/history/ledger-archive.md`:
- If it exceeds 100 entries (count `## Entry:` headers), compact: summarize the oldest 80% into a block summary, keep the newest 20% as individual entries
- This prevents the archive from growing unboundedly as skills overwrite their ledger sections over many cycles

See [references/context-ledger-spec.md](./references/context-ledger-spec.md) for the full ledger protocol.

### Phase 4 — Mark Report as Applied

Add to the top of the processed drift report:

```markdown
**Status:** APPLIED
**Applied by:** charter
**Applied at:** {timestamp}
```

This prevents charter from reprocessing the same report.

### Phase 5 — Summary

Present the user with a summary:

```
Charter applied {N} updates from scout report {filename}:
- Structural: {count} changes
- Convention: {count} updates
- Dependency: {count} changes
- Interface: {count} changes
- Smells logged: {count}

Memory advanced to commit {hash}.
History compaction: {compacted/not needed}
```

---

## Ground Rules

- **Depends on scout** — charter cannot run standalone. It requires scout's output (drift reports) and scout's presence in the skills directory. If either is missing, charter exits immediately.
- **Never modify without approval** — charter requires a reviewed scout report with all `[DECIDE]` items resolved. No exceptions.
- **Preserve prescriptive style** — when updating conventions, maintain the "always do X" format with concrete code examples. Don't weaken conventions into descriptions.
- **Smells are not failures** — smells are tracked for pattern detection, not for shaming. If a smell repeats enough, it becomes a convention discussion.
- **Compaction preserves signal** — compacted summaries retain enough context for charter to detect recurring patterns across reports.
- **Idempotent** — running charter on an already-applied report does nothing (detects `APPLIED` status and exits).
- **One report at a time** — charter processes a single drift report per invocation. For multiple pending reports, process them in chronological order.
- **Track progress** — use task management tools to give the user visibility into each phase.
