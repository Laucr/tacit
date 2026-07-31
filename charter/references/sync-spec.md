# Sync Specification

Reference document for charter's update and compaction logic. Explains the memory structure, update rules, compaction strategy, and file format specs.

---

## Memory Structure

Charter manages this directory tree in the target project:

```
.claude/
├── memory/
│   ├── current.md                          # ≤200 lines, latest state snapshot
│   └── history/
│       ├── drift/
│       │   ├── main-a3f2c1d-20260403T1430.md   # Individual drift reports
│       │   ├── main-b4e3d2e-20260404T0900.md
│       │   ├── _compacted-20260401.md           # Compacted summary of older reports
│       │   └── ...
│       └── smells-archive.md                    # Archived smell entries from current.md
├── rules/
│   └── {project}-dev-conventions.mdc        # Convention rules (updated by charter)
└── analyses/
    └── conventions.md                       # Detailed conventions with examples
```

---

## File Formats

### current.md

The state snapshot. Updated by charter after each applied drift report.

```markdown
# Scout Baseline

**Branch:** main
**Commit:** a3f2c1d
**Full hash:** a3f2c1d4e5b6c7d8e9f0a1b2c3d4e5f6a7b8c9d0
**Date:** 2026-04-03T14:30
**Last updated by:** charter from report main-a3f2c1d-20260403T1430.md

## Known Smells

| Date | Commit | Type | File | Description |
|------|--------|------|------|-------------|
| 2026-04-03 | a3f2c1d | error_handling | pkg/api/handler.go:42 | Uses fmt.Errorf but convention says errors.Wrap |

## Update History

| Date | Commit | Report | Changes Applied |
|------|--------|--------|----------------|
| 2026-04-03 | a3f2c1d | main-a3f2c1d-20260403T1430.md | 3 structural, 2 convention, 1 dep |
```

**Size cap:** 200 lines. When exceeded, charter trims "Known Smells" to 20 most recent entries and archives the rest.

### Applied drift report header

Charter adds this to the top of processed reports:

```markdown
**Status:** APPLIED
**Applied by:** charter
**Applied at:** 2026-04-03T15:00
```

### Compacted history file

When compaction triggers, older reports are summarized:

```markdown
# Compacted Drift History

Compacted on: 2026-04-10T12:00
Reports covered: 8 reports from 2026-03-15 to 2026-04-05

| # | Date | Commit | Severity | Structural | Convention | Dependency | Interface | Status |
|---|------|--------|----------|------------|------------|------------|-----------|--------|
| 1 | 2026-03-15 | b2e4f6a | minor | 1 | 0 | 0 | 2 | APPLIED |
| 2 | 2026-03-20 | c3f5g7b | moderate | 3 | 2 | 1 | 0 | APPLIED |
| ... | | | | | | | | |

## Recurring Patterns

- error_handling drift detected in 4/8 reports → convention was updated on 2026-03-25
- New packages added in 6/8 reports → active development in pkg/features/
```

### Smells archive

When current.md smells are trimmed:

```markdown
# Archived Smells

Archived on: 2026-04-10T12:00
Entries: 35 (from 2026-02-01 to 2026-03-30)

| Date | Commit | Type | File | Description |
|------|--------|------|------|-------------|
| 2026-02-01 | x1y2z3a | logging | pkg/old/server.go:15 | Uses fmt.Println |
| ... | | | | |
```

---

## Update Rules

### What charter updates per category

**Structural changes (`[UPDATE]`):**
- `.mdc` rules file → "Where to Work" section
  - New packages: add package name + brief purpose
  - Removed packages: remove from list
  - Renames: update old name → new name

**Convention changes (`[UPDATE]`):**
- `.mdc` rules file → "How to Work" section
  - Replace the old pattern with the new pattern
  - Keep prescriptive voice: "always use X" not "X is now used"
- `.claude/analyses/conventions.md`
  - Update the code example for the affected convention area
  - Include the new import path if it changed
  - Reference a source file showing the new pattern

**Dependency changes:**
- Only update conventions if the dependency affects coding patterns
  - New logger library → update logging convention
  - New error library → update error handling convention
  - New ORM → update data access convention
- Otherwise: note in `current.md` update history only

**Interface changes (`[UPDATE]`):**
- `.mdc` rules file → update any references to changed signatures
- `.claude/analyses/conventions.md` → update code examples if they use the changed symbols

### What charter skips

- `[SMELL]` items → logged in `current.md` "Known Smells" table, no convention change
- Low-severity structural items (file_modified) → no convention update needed
- Dependency patch bumps → no convention update unless API changed

---

## Compaction Strategy

### Trigger

Compaction runs automatically at the end of every charter invocation.

Check: count files in `.claude/memory/history/drift/` (excluding `_compacted-*.md` files).

- **≤10 reports** → no compaction needed
- **>10 reports** → compact the oldest 80%, keep newest 20%

### Process

1. List all non-compacted drift report files, sorted by timestamp
2. Calculate split point: keep the newest `ceil(count * 0.2)` files
3. For each file to compact:
   - Extract: date, commit, overall severity, category counts, status (APPLIED or not)
   - Delete the individual report file
4. Append the summary rows to `_compacted-{date}.md`
   - If the compacted file already exists, append to it
   - If not, create it with the header template
5. Scan compacted entries for recurring patterns (same convention type appearing in 3+ reports)
   - Add to the "Recurring Patterns" section

### current.md trimming

Runs after compaction.

1. Count lines in `current.md`
2. If >200 lines:
   - Count rows in "Known Smells" table
   - If >20 rows: move oldest entries to `history/smells-archive.md`
   - Keep only the 20 most recent smell entries

---

## Scripts

| Script | Purpose | Input | Output |
|--------|---------|-------|--------|
| `scripts/parse_report.js` | Extract actionable items from a drift report | Report file path | JSON: `{updates, smells, undecided}` |
| `scripts/compact_history.js` | Compact old drift reports | History directory path | Compacted file + deleted old reports |

### parse_report.js

```bash
node scripts/parse_report.js <report.md>
```

Output:
```json
{
  "report": "main-a3f2c1d-20260403T1430.md",
  "commit": "a3f2c1d",
  "branch": "main",
  "severity": "moderate",
  "updates": [
    {"category": "structural", "action": "Update structural map: new package pkg/newfeature"},
    {"category": "convention", "action": "Update convention: error handling → fmt.Errorf"}
  ],
  "smells": [
    {"category": "convention", "action": "Ignored error in pkg/api/handler.go:42"}
  ],
  "undecided": []
}
```

Exit codes:
- `0` — all decisions resolved
- `1` — undecided items remain

### compact_history.js

```bash
node scripts/compact_history.js <history-dir> [--threshold 10] [--keep-ratio 0.2]
```

Output: JSON summary of what was compacted
```json
{
  "compacted": 8,
  "kept": 2,
  "compacted_file": "_compacted-20260410.md",
  "recurring_patterns": ["error_handling (4/8)", "package additions (6/8)"]
}
```

Exit codes:
- `0` — compaction performed or not needed
- `1` — error during compaction
