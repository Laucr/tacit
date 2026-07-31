# Context Ledger Specification

A shared protocol for cross-skill context exchange. The context ledger is a single file at `.claude/memory/context-ledger.md` that skills read before starting and write to on completion.

---

## Purpose

Skills in the dev workflow operate independently but make better decisions when they know what happened in previous cycles:

- **Blueprint** avoids proposing patterns that bailiff rejected
- **Builder** knows what blueprint intended and what bailiff rejected
- **Bailiff** knows what builder chose to deviate on and what smells scout tracked
- **Inquest** knows the design rationale (blueprint), the acknowledged divergences (builder), and the last verdict (bailiff) — so it can tell "known deviation" from "new finding" during triage or smoke diagnosis
- **Scout** can distinguish planned changes (from blueprint) from accidental drift

The ledger provides this cross-skill awareness without coupling skills directly.

---

## File Location

```
.claude/memory/context-ledger.md
```

Created on first write by any participating skill. If `.claude/memory/` doesn't exist, the skill should create it (scout already handles this during bootstrap).

---

## Format

```markdown
# Context Ledger

Last updated: {date} by {skill-name}

## Blueprint (cap: 15 lines)

Active PRDs and key design decisions. Overwritten each blueprint run.

- **{slug}** ({date}, {commit}): {key decisions, comma-separated}
- **{slug}** ({date}, {commit}): {key decisions}
- **Deferred**: {items pushed to future cycles}

## Builder (cap: 10 lines)

Latest build cycle notes. Overwritten each builder run.

- **{slug}** ({date}, {commit}): {implementation choices}
- **Diverged from plan**: {what and why}
- **Tech debt**: {acknowledged shortcuts}

## Bailiff (cap: 10 lines)

Recent verification results. Overwritten each bailiff run, keeps last 3 verdicts.

- **{slug}** ({date}, {commit}): {verdict} — {key findings}

## Inquest (cap: 10 lines)

Latest inquest runs (triage and smoke). Overwritten each inquest run, keeps last 3 entries.

- **{slug}** ({date}, {commit}): triage — fixed={F} rejected={R} deferred={D} → {next step}
- **{slug}** ({date}, {commit}): smoke — {diagnosis} → {next step}
```

---

## Rules

### Overwrite, don't append

Each skill **overwrites** its own section entirely on each run. The ledger is a snapshot of the current state, not a log. History is preserved in the archive (see below).

### Caps

| Section | Cap | Enforced by |
|---------|-----|-------------|
| Blueprint | 15 content lines | blueprint skill |
| Builder | 10 content lines | builder skill |
| Bailiff | 10 content lines | bailiff skill |
| Inquest | 10 content lines | inquest skill |
| **Total** | **~45 content lines** | — |

Content lines = lines between the section header and the next section header, excluding blank lines. The cap is enforced by the writing skill — if your update would exceed the cap, trim the oldest entries first.

### Read before write

Every participating skill must:

1. **Read** the full ledger before starting work (if it exists)
2. Use relevant sections to inform decisions
3. **Overwrite** only its own section on completion
4. Never modify another skill's section

### Section ownership

| Section | Written by | Read by |
|---------|-----------|---------|
| Blueprint | blueprint | builder, bailiff, inquest, scout |
| Builder | builder | bailiff, inquest, scout |
| Bailiff | bailiff | blueprint, builder, inquest |
| Inquest | inquest | blueprint, builder, bailiff |

Scout reads the ledger but does not write to it — its output goes to `.claude/memory/current.md` and drift reports.

Charter does not have a ledger section — its state is in `current.md` and the drift reports.

---

## Archive

When a skill overwrites its section, the **old content** is automatically appended to:

```
.claude/memory/history/ledger-archive.md
```

Format:

```markdown
# Ledger Archive

## Entry: blueprint @ 2026-04-01T14:30

- **auth-v2** (2026-04-01, a1b2c3d): JWT with refresh tokens, stateless middleware
- **Deferred**: WebSocket support pushed to Q3

## Entry: builder @ 2026-04-02T10:00

- **auth-v2** (2026-04-02, b2c3d4e): Used chi middleware chain
- **Diverged from plan**: Refresh token in DB instead of Redis
```

Charter compacts this archive using the same strategy as drift history — when it exceeds a threshold, summarize older entries.

---

## Integration Instructions per Skill

### Blueprint

**Before Phase 1** (exploring codebase):
1. Read `.claude/memory/context-ledger.md` if it exists
2. Check the **Bailiff** section for recent failures — avoid proposing patterns that were rejected
3. Check the **Builder** section for tech debt notes — factor them into the new design

**After Phase 5** (summary):
1. Read the current ledger
2. Archive the old Blueprint section to `history/ledger-archive.md`
3. Overwrite the Blueprint section with:
   - One line per PRD: slug, date, commit, key decisions
   - One "Deferred" line if applicable
4. Update the `Last updated` header

### Builder

**Before Step 3** (exploring codebase):
1. Read `.claude/memory/context-ledger.md` if it exists
2. Check the **Blueprint** section for design decisions and rationale
3. Check the **Bailiff** section for past failures on the same spec — avoid repeating them

**After Step 7** (summary):
1. Read the current ledger
2. Archive the old Builder section to `history/ledger-archive.md`
3. Overwrite the Builder section with:
   - One line per implemented spec: slug, date, commit, notable choices
   - One "Diverged from plan" line if applicable
   - One "Tech debt" line if applicable
4. Update the `Last updated` header

### Bailiff

**Before Phase 1** (building expectation checklist):
1. Read `.claude/memory/context-ledger.md` if it exists
2. Check the **Builder** section for acknowledged divergences — these are known, not failures
3. Check the **Blueprint** section for design rationale — helps interpret ambiguous spec items

**After Phase 4** (verdict):
1. Read the current ledger
2. Archive the old Bailiff section to `history/ledger-archive.md`
3. Overwrite the Bailiff section with:
   - One line per verified spec: slug, date, commit, verdict, key findings
   - Keep last 3 verdicts maximum
4. Update the `Last updated` header

### Inquest

**Before Step 1** (mode selection):
1. Read `.claude/memory/context-ledger.md` if it exists
2. Check the **Blueprint** section for design rationale — disambiguates spec §s when a finding cites one
3. Check the **Builder** section for acknowledged divergences — these are known deviations, not fresh findings to triage
4. Check the **Bailiff** section for the last verdict — in triage mode, this is where the report under triage originated; in smoke mode, it tells you what was verified against which PRD version

**After Step 8** (both modes):
1. Read the current ledger
2. Archive the old Inquest section to `history/ledger-archive.md`
3. Overwrite the Inquest section with:
   - For triage runs: `- **{slug}** ({date}, {commit}): triage — fixed={F} rejected={R} deferred={D} → {next step}`
   - For smoke runs: `- **{slug}** ({date}, {commit}): smoke — {diagnosis} → {next step}`
   - Keep last 3 entries maximum
4. Update the `Last updated` header

### Scout

**During Phase 2** (convention drift):
1. Read `.claude/memory/context-ledger.md` if it exists
2. Check the **Blueprint** section — if a drift finding matches a blueprint decision, annotate it in the report as `[PLANNED]` instead of `[DECIDE]`. Planned changes are intentional, not drift.

Scout does not write to the ledger.

### Charter

**During Phase 3** (compact history):
1. Check `history/ledger-archive.md` size
2. If it exceeds 100 entries, compact: summarize the oldest 80%, keep newest 20%

Charter does not have its own ledger section.

---

## Bootstrapping

The ledger is created lazily — the first skill to complete after the ledger protocol is adopted will create it. If `.claude/memory/context-ledger.md` doesn't exist when a skill tries to read it, the skill simply skips the read step (no error).

No migration is needed for existing projects. The ledger starts empty and fills as skills run.
