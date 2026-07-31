---
name: builder
description: Implement features from a specification document — PRD, implementation plan, or any structured requirements doc. Works seamlessly with blueprint skill outputs (.claude/prds/ and .claude/plans/) but also handles standalone spec files. Use this skill whenever the user wants to implement a feature from a spec, build from a PRD, execute an implementation plan, or asks to "build this" or "implement this" with a reference to a requirements document.
---

# Builder

Implement features by following a specification document. This skill reads a requirements doc (PRD, implementation plan, or any structured spec), understands what needs to be built, and writes the code.

It works in two modes:

1. **With blueprint artifacts** — When the user has previously run the `blueprint` skill, the PRD lives at `.claude/prds/<slug>.md` and the plan at `.claude/plans/<slug>.md`. Builder reads both and uses the plan's concrete steps to drive implementation.
2. **Standalone** — When given any spec file (a PRD, a design doc, a requirements markdown, etc.), Builder reads it, explores the codebase, and derives implementation tasks from the spec's content.

## Workflow

### Step 1: Load the Spec

The user will reference a spec file — either by path or by describing what they want to build from.

1. **Locate the file.** If the user gives a path, use it. If they reference a slug or feature name, check `.claude/prds/` and `.claude/plans/` for matching files.
2. **Identify the document type** by its content:
   - **Plan** (contains The Problem, The Approach, The Work with phased items) — a concrete implementation guide with file-level instructions and progress markers (`*` done, `+` done later, `-` decided against, unmarked = open).
   - **PRD** (contains Overview, Goals, Technical Design) — a requirements document describing *what* to build.
   - **Other spec** — any structured document with requirements, acceptance criteria, or design details.
3. **Load companion artifacts** when available:
   - If a plan was loaded and it references a PRD (via a `PRD:` field), read the PRD for full context on requirements and constraints.
   - If a PRD was loaded, check `.claude/plans/` for a matching plan. If found, use it — the plan has concrete steps that save time.
4. Note any additional instructions the user provided — they take priority for scoping.

### Step 2: Load Project Rules

1. Check for `.claude/rules` in the current working directory.
2. If rules exist, read them. All rules found there must be followed during implementation.

### Step 2.5: Read the Context Ledger

If `.claude/memory/context-ledger.md` exists, read it before exploring:
- Check the **Blueprint** section for design decisions and rationale — understand *why* the spec chose a particular approach.
- Check the **Bailiff** section for past failures on the same spec — avoid repeating mistakes from previous build cycles.

If the file doesn't exist, skip this step.

### Step 2.6: Drift pre-flight (optional)

If `plumb` is available, run it before starting implementation
(`python ../plumb/scripts/drift_check.py --feature <slug>`). It reads
the frontmatter on the PRD, plan, and any existing build/bailiff reports and
prints a per-feature alignment table.

- **Plan `prd_version` matches the live PRD `version`** → proceed.
- **Plan is STALE** (PRD has moved past the version the plan was aligned to)
  → stop and surface to the user. Suggested response: "the plan is N PRD revs
  stale; want me to run `pivot` first?" Do NOT silently re-derive the plan from
  the PRD — that erases the user's review of the prior plan.
- **WARN / UNKNOWN / LEGACY** (frontmatter missing or partial) → proceed,
  but note in the build report that drift could not be checked precisely.

If `plumb` is not available, do the equivalent by hand: read the PRD
and plan, see whether the plan still describes what the PRD now says.

### Step 3: Explore the Codebase

Before writing any code, understand the existing codebase:

- Use `Glob`, `Grep`, `Read`, and `Agent` (Explore) to understand project structure, conventions, and patterns.
- **When a plan exists**, read the specific files listed in each step's `Files:` section. Verify they still exist and match the plan's assumptions.
- **When working from a PRD or other spec**, perform broader exploration:
  - Identify files that will need to be created or modified based on the technical design.
  - Trace call chains for listed dependencies.
  - Find similar features in the codebase to use as implementation references.
- Understand existing patterns for naming, error handling, testing, configuration, and dependencies.

### Step 4: Plan the Implementation

1. **When a plan exists**, use its steps directly as implementation tasks. Each step in the plan becomes a task.
2. **When working from a PRD or other spec**, break the requirements into concrete implementation tasks:
   - Derive tasks from the technical design sections.
   - Include tasks for error handling described in the spec.
   - Include testing tasks based on the spec's goals and the codebase's test patterns.
3. Use `TaskCreate` to track each task.
4. If the user's instructions narrow the scope, only plan tasks relevant to that scope.
5. If any part of the spec is unclear or ambiguous, use `AskUserQuestion` to clarify before proceeding.

### Step 5: Implement

For each task, in order:

1. Mark the task as `in_progress` with `TaskUpdate`.
2. Write the code, following:
   - **Plan steps** (if available) — the plan specifies which files to modify and what changes to make.
   - **Spec requirements** — the spec is the source of truth for *what* the feature should do.
   - **Project rules** from `.claude/rules`.
   - **Existing codebase conventions** and patterns.
3. Prefer editing existing files over creating new ones.
4. When the plan references specific functions, structs, or patterns, verify they still exist before using them.
5. Mark the task as `completed` when done.

### Step 6: Verify

After all implementation tasks are complete:

1. If the plan has a **Testing** section, follow it — run the suggested tests or create the test files it specifies.
2. If the spec has open questions that affect implementation, flag them to the user.
3. Check for any trade-offs from the plan that materialized during implementation.

### Step 7: Build Report & Ledger Update

Write a build report and present it to the user.

1. Read `references/build-report-template.md` and fill it in. **Set the frontmatter:** `prd_version` and `plan_version` capture exactly what this build was implemented against — those are the values `plumb` will compare to the live PRD/plan to decide whether the build report is stale. The report follows a BurntSushi PR style:
   - **State the problem clearly** — what the spec required and why it matters.
   - **Specify exact behavior** — what the system now does, concretely.
   - **Name tradeoffs and downsides up front** — tech debt, performance costs, limitations.
   - **Keep scope tight** — document what you did *not* do and why.
   - **Note deviations from the plan** — what changed vs. what the plan said, and the reasoning.
   - **Optimize for maintainability** — write enough that a reviewer can judge intent quickly.
2. Write the report to `.claude/reports/<slug>-build.md`.
3. Present the report content to the user in chat as well.

After presenting the summary, update the context ledger:

1. Read `.claude/memory/context-ledger.md` (create it if it doesn't exist)
2. If the Builder section already has content, append the old content to `.claude/memory/history/ledger-archive.md` with an `## Entry: builder @ {timestamp}` header
3. Overwrite the Builder section with:
   - One line per implemented spec: `- **{slug}** ({date}, {commit}): {notable implementation choices}`
   - One `- **Diverged from plan**: {what and why}` line if applicable
   - One `- **Tech debt**: {acknowledged shortcuts}` line if applicable
4. Update the `Last updated:` header line
5. Keep the section within 10 content lines — if it exceeds, drop the oldest entries

See [charter/references/context-ledger-spec.md](../charter/references/context-ledger-spec.md) for the full ledger protocol.

## Guidelines

- **Follow the spec faithfully.** Implement what the spec says — no more, no less.
- **Follow the plan when available.** The plan is a concrete guide — respect its structure and file-level decisions.
- **Respect project rules.** Always check `.claude/rules` and adhere to them.
- **Ask when uncertain.** If the spec is ambiguous, ask the user rather than guess.
- **Explore before coding.** Understand existing code patterns before writing new code.
- **Keep it simple.** Avoid over-engineering. Implement the minimum needed to satisfy the requirements.
- **Track progress.** Use task management tools to give the user visibility into progress.
- **Handle drift gracefully.** If the codebase has changed since the plan was written (files moved, functions renamed), adapt the plan's intent to the current state rather than failing.
