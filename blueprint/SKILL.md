---
name: blueprint
description: A PRD-then-Plan workflow for pre-implementation design. Explores the codebase, drafts a PRD, iterates with the user, then produces an implementation plan. Never writes implementation code. Use this skill whenever the user wants to plan a feature, design an API, prepare before coding, discuss requirements, write a PRD, or create an implementation plan — even if they don't explicitly say "blueprint".
---

# Pre-Implementation Design

A handbook for conducting pre-implementation design sessions. The goal is to explore the codebase, understand requirements, produce a PRD, then produce an implementation plan — all through dialogue with the user. **No implementation code is written during this workflow.**

## Output Locations

- PRD: `.claude/prds/<slug>.md` (in the current working directory)
- Plan: `.claude/plans/<slug>.md` (in the current working directory)

Where `<slug>` is a short kebab-case name derived from the feature description.

## Frontmatter contract

Every PRD and plan MUST start with the YAML frontmatter shown in the templates.
The `version`, `prd_version`, and `last_aligned` fields drive drift detection
across the loop. Rules:

- **PRD `version`**: bump on any requirements change. Minor bump for
  clarifications/additions. Major bump for pivots that invalidate the plan.
- **Plan `prd_version`**: must equal the current PRD's `version` at the moment
  the plan was reconciled. If you edit the plan in response to a PRD change,
  sync this field — that is the entire signal for "plan is current."
- **`last_aligned`**: today's date whenever you touch the file in a way that
  bumps `version` or syncs `prd_version`.
- **`status`**: `current` while in use, `superseded` after a `pivot` run.

The `pivot` skill handles all of this automatically when requirements change.
For manual edits, bump `version` (minor) and refresh `last_aligned`.

## Templates

- **PRD template:** Read [references/prd-template.md](./references/prd-template.md) when drafting the PRD.
- **Plan template:** Read [references/plan-template.md](./references/plan-template.md) when drafting the implementation plan.

---

## Phase 1: Understand Requirements & Explore Codebase

**Goal:** Gather enough context to draft a PRD.

### Step 0: Read the context ledger

If `.claude/memory/context-ledger.md` exists, read it before exploring:
- Check the **Bailiff** section for recent failures — avoid proposing patterns that were rejected in previous cycles.
- Check the **Builder** section for tech debt notes — factor acknowledged shortcuts into the new design.

If the file doesn't exist, skip this step.

### Step 1: Triage the request

Users come in with wildly different levels of detail. Before diving into codebase exploration, assess what you're working with:

| Input type | Example | Your job |
|---|---|---|
| **Vague / high-level** | "build me a search feature" | You drive the design. Explore the codebase heavily, propose the architecture, surface decisions the user needs to make. |
| **Constraint-style** | "I need an API that calls service X, returns top N results, with a timeout of 3s" | The user knows *what* they want but not *how* it fits. Capture their constraints as-is, then figure out the wiring — where it lives, what patterns to follow, what's reusable. |
| **Detailed spec** | A full description with endpoints, fields, and behavior | Validate against the codebase. Check feasibility, flag conflicts with existing code, fill in gaps. |

The key insight: regardless of input type, the codebase exploration in Step 2 is what fills the gaps. A vague request just means more gaps to fill. Don't bombard the user with questions upfront — explore first, then ask informed questions.

### Step 2: Explore the codebase

Use `Glob`, `Grep`, `Read`, and `Agent` (Explore) to understand:
- Project structure and tech stack
- Existing code related to the feature domain (similar APIs, models, services)
- Patterns and conventions (naming, error handling, config, testing)
- External dependencies and integrations

For vague/constraint-style requests, pay extra attention to:
- **Similar features already in the codebase** — these are your best guide for proposing architecture the user hasn't specified
- **Call chains** — if the user mentioned a downstream service, trace how existing code calls similar services
- **Proto definitions / API patterns** — what does a typical endpoint look like in this project?

### Step 3: Draft the PRD

Read `references/prd-template.md`, fill it in, and write the result to `.claude/prds/<slug>.md`. The template has optional sections — skip what doesn't apply (e.g., a simple API wrapper may not need "User Stories").

**Set the frontmatter:** `feature: <slug>`, `artifact: prd`, `version: 1.0`,
`last_aligned: <today>`, `status: current`. Use stable section IDs (`§3.2`,
`§4.1`) — plans, build reports, and bailiff checklists will reference them.

For vague requests: you're *proposing* the design, not just documenting it. Make your reasoning visible — explain why you chose a particular approach based on what you found in the codebase.

For constraint-style requests: capture the user's stated constraints verbatim in the "Constraints" section, then build the rest of the design around them.

### Step 4: Present to the user

- What you understood from the requirements (and what you inferred)
- What you found in the codebase that shaped the design
- Key questions or ambiguities — especially decisions the user needs to make
- A note that the PRD has been written to disk

---

## Phase 2: PRD Review Loop

**Goal:** Iterate on the PRD until the user confirms it.

1. After presenting the PRD summary, use `AskUserQuestion` to ask:
   - "Does the PRD look good, or do you have changes/answers to the open questions?"
   - Provide options: "Looks good, proceed to plan" / "I have feedback"
2. If the user has feedback:
   - Update the PRD file (increment version, update fields)
   - **Bump `version` in the frontmatter** (minor for edits, major for pivots) and refresh `last_aligned`. If the change is a pivot — anything that would invalidate an existing plan or build — prefer running the `pivot` skill instead, which handles downstream artifacts too.
   - Present the changes
   - Loop back to step 1
3. If the user confirms: proceed to Phase 3.

---

## Phase 3: Explore Implementation Details & Draft Plan

**Goal:** Produce a concrete implementation plan.

1. Now that requirements are locked, dive deeper into the codebase:
   - Read the specific files that will need modification
   - Understand function signatures, struct definitions, and call chains
   - Identify test patterns and where new tests should go
   - Look at config files, build files, and deployment setup
2. Read `references/plan-template.md`, fill it in, and write the result to `.claude/plans/<slug>.md`. **Set the frontmatter:** `prd_version` MUST equal the PRD's current `version`; that is the drift signal. Reference PRD sections by their stable IDs (`Phase 2 implements §3.2, §4.1`) so drift-mode bailiff and `pivot` can map plan phases to PRD sections mechanically. The plan follows a Carmack .plan style:
   - **Be direct.** Lead with the decision, then show reasoning. No filler.
   - **Show alternatives considered** and why they were rejected.
   - **Be honest about trade-offs** — name costs and how you'll deal with them.
   - **Use progress markers** in the work list: `*` done, `+` done later, `-` decided against, unmarked = still open.
   - **Write like a working engineer**, not a committee. One voice, precise language, no jargon theater.
3. Present a summary to the user:
   - The problem and the approach (with reasoning, not just the conclusion)
   - Key trade-offs and what we accept
   - What we're explicitly not doing

---

## Phase 4: Plan Review Loop

**Goal:** Iterate on the plan until the user confirms it.

1. After presenting the plan summary, use `AskUserQuestion` to ask:
   - "Does the plan look good, or do you have changes?"
   - Provide options: "Looks good, plan is finalized" / "I have feedback"
2. If the user has feedback:
   - Update the plan file
   - Present the changes
   - Loop back to step 1
3. If the user confirms: proceed to Phase 5.

---

## Phase 5: Summary & Ledger Update

Both documents are finalized. Present:

1. Final PRD location: `.claude/prds/<slug>.md`
2. Final Plan location: `.claude/plans/<slug>.md`
3. A concise summary of what was decided
4. Suggested next step: "You can now implement this plan. The plan file can be used as input to Claude Code or EnterPlanMode."

After presenting the summary, update the context ledger:

1. Read `.claude/memory/context-ledger.md` (create it if it doesn't exist)
2. If the Blueprint section already has content, append the old content to `.claude/memory/history/ledger-archive.md` with an `## Entry: blueprint @ {timestamp}` header
3. Overwrite the Blueprint section with:
   - One line per PRD: `- **{slug}** ({date}, {commit}): {key decisions}`
   - One `- **Deferred**: {items}` line if any items were pushed to future cycles
4. Update the `Last updated:` header line
5. Keep the section within 15 content lines — if it exceeds, drop the oldest PRD entries

See [charter/references/context-ledger-spec.md](../charter/references/context-ledger-spec.md) for the full ledger protocol.

---

## Guidelines

- **Never write implementation code.** Your output is PRD and plan documents only.
- **Be question-driven.** When uncertain, ask the user rather than assume.
- **Explore before proposing.** Always check existing code patterns before suggesting new ones. Reuse existing abstractions, naming conventions, and error handling patterns.
- **Keep documents concise.** Prefer bullet points over paragraphs. Omit sections that don't apply.
- **Respect the user's time.** Batch your questions — ask several at once rather than one at a time.
- **Update files on disk.** Every revision should be written to the file, not just discussed in chat.
