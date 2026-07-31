---
name: warmup
description: Warm up to an unfamiliar Go codebase — explore its structure, extract coding conventions, and distill them into a Claude-compatible development rule file. Use this skill whenever you're dropped into a new Go repository, asked to onboard to a project, set up development rules, analyze repo conventions, or need to understand "how things work here" before writing code. Even if the user just says "get familiar with this repo" or "figure out the patterns", this is the right skill.
allowed-tools: Read, Write, Bash, Grep, Glob, Agent
---

Warm up to a new Go repository by understanding its structure, extracting its conventions, and distilling both into actionable development references — so that all future work follows the project's established patterns.

This is a 3-phase process. Each phase produces a file. Present each to the user for review before moving on — their confirmation gates the next phase.

## Phase 1 — Map the Terrain

Explore the repo and write `.claude/analyses/repo_structure.md`.

Use parallel Explore agents to cover ground quickly. Capture:

1. **Directory classification** — list top-level directories, mark each as *core* (actively developed) or *supporting* (config, scripts, vendored, generated)
2. **Entry points** — main packages, bootstrap files, initialization sequences
3. **Execution paths** — HTTP handlers, gRPC services, message consumers, background workers, cron/timers
4. **Architecture** — key interfaces, layering patterns (handler → service → repo), data flow between components
5. **External dependencies** — databases, caches, message brokers, upstream/downstream services

Present findings to the user. Wait for their go-ahead before proceeding.

## Phase 2 — Extract Conventions

Read representative source files across multiple core packages (not just one) and write `.claude/analyses/conventions.md`.

Cover these areas:

| Area | What to capture |
|---|---|
| **Type definitions** | Struct tag conventions (e.g., dual `json` + `bson`), naming patterns, interface design, domain constants |
| **Error handling** | Error wrapping/propagation, sentinel errors, error codes, control flow patterns |
| **API design** | Request/response shapes, validation approach, pagination, async patterns |
| **Constants** | Naming style, organization (grouped vs scattered), explicit values vs `iota` |
| **Logging** | Logger import paths, context-aware log functions, structured fields, message format |
| **Context** | How `context.Context` propagates, cloning for background goroutines, metadata extraction |
| **Data access** | DAO/repository patterns, cursor management, bulk operations, transaction handling |

For each area: one or two sentences explaining the convention, then a concrete code snippet with import paths. Always reference the source file path so the convention is traceable.

Be specific — "dual `json` + `bson` tags on all MongoDB model structs" beats "tags are used". Be prescriptive — "always wrap errors with `fmt.Errorf(...: %w)`" beats "error wrapping varies".

Present findings to the user. Wait for their go-ahead before proceeding.

## Phase 3 — Distill the Rules

Combine Phase 1 and Phase 2 into a single Claude rule file at `.claude/rules/{project-name}-dev-conventions.mdc`:

```yaml
---
description: Development conventions for {project}
globs: "**/*.go"
---
```

Structure the rule in two sections:

- **Where to Work** — package classification, entry points, execution paths (distilled from Phase 1)
- **How to Work** — conventions for types, errors, APIs, constants, logging, context, data access (distilled from Phase 2)

End with a pointer to the full analysis:

```
<!-- Detailed conventions with full examples: .claude/analyses/conventions.md -->
```

Keep it concise, prescriptive, and scannable. Bullet points. Every line actionable. This file will live in Claude's context for every future edit — make each word earn its place.

## Ground Rules

- Sample broadly — read from multiple core packages to avoid bias toward one area
- Specificity over generality — name the exact patterns, imports, and tag styles you find
- Prescriptive over descriptive — "always do X" not "X is sometimes done"
- Gate each phase — produce the file, present it, wait for user review before continuing
- Speed matters — use parallel Explore agents wherever independent analysis can overlap
