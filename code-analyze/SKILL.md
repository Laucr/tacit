---
name: code-analyze
description: An architectural code analysis tool designed to onboard developers, facilitate refactoring, and guide migration strategies through structural decomposition.
allowed-tools: Read, Write, Bash, Grep, Glob, Agent, AskUserQuestion
---

# Code Analysis

Dissect a codebase to reveal its architecture, data flow, and dependencies. Produce a structured report suitable for onboarding new developers, planning refactoring efforts, or documenting system design.

This is a 6-phase process. Each phase gates the next — present findings to the user and get confirmation before moving on.

**Prerequisites:** `tokei` must be installed for codebase metrics. Run `scripts/check_prerequisites.sh` (Phase 0) to verify.

**Output:** Reports are written to `.claude/analyses/{timestamp}_{level}_{target}.md` in the target project.

---

## Phase 0 — Prerequisites

Validate that required tools are available before starting analysis.

**Step 1:** Run the prerequisite check script:

```bash
bash <skill-dir>/scripts/check_prerequisites.sh <target-directory>
```

This outputs JSON with:
- `ok` — whether all required tools are present
- `missing` — list of missing tools with install instructions
- `detected_stack` — one of `go` or `generic`

**Step 2:** If `ok` is false, present the missing tools and install instructions to the user. Do not proceed until prerequisites are met.

**Step 3:** Store `detected_stack` for Phase 2 discovery strategy.

---

## Phase 1 — Scoping (Interactive)

Ask the user what they want analyzed. Use `AskUserQuestion` to collect three decisions:

### Question 1: Analysis Level

| Level | What it covers |
|-------|---------------|
| **Project** | High-level architecture — all entry points, end-to-end request paths, observability |
| **API** | Single endpoint deep dive — lifecycle, dependencies, data flow |
| **Module** | Domain logic group — business rules, state changes, inter-module deps |
| **Function** | Specific functions — complexity, call stack, data mutation |

### Question 2: Target

- **Project level:** target = entire repository (no further input needed)
- **API level:** which endpoint/route/RPC method?
- **Module level:** which package or domain area?
- **Function level:** which function(s) by name?

If the user is unsure, run a quick exploration to list available targets and let them pick.

### Question 3: Depth

| Mode | Trace Depth | Flowcharts | Metrics | Best For |
|------|------------|------------|---------|----------|
| **Quick** | 2 levels | No | Top-level only | Fast overview, status check |
| **Deep** | 5 levels | Yes (Mermaid) | Full breakdown | Onboarding, refactoring, documentation |

Store the three choices: `{level}`, `{target}`, `{depth}`.

---

## Phase 2 — Discovery

Explore the codebase using a stack-aware strategy. Use parallel Explore agents to cover ground quickly.

### Go Stack

If `detected_stack` is `go`:

1. Find `main.go` or `cmd/` entry points
2. Grep for HTTP/gRPC server bootstrap (`http.ListenAndServe`, `grpc.NewServer`)
3. Search for route registrations (`http.Handle`, `mux.`, `chi.`, `gin.`)
4. Look for `internal/`, `pkg/`, `cmd/` standard Go layout
5. Check `go.mod` for framework, transport, storage, and observability dependencies
6. Glob `**/*.proto` and parse any service and method declarations
7. Infer architectural layers from package names, imports, constructors, and call paths; do not assume a standard directory layout

### Generic Stack (Fallback)

If `detected_stack` is `generic`:

1. Find entry points: `glob **/main.*`, look for server bootstrap patterns
2. Grep for route, endpoint, consumer, job, and command registrations using patterns found in manifests and dependencies
3. Look for config files: `glob **/*.yaml **/*.yml **/*.toml **/*.json` in root and config directories
4. Identify the layering pattern from directory names and import structure

### Discovery Output

Present findings to the user:
- Detected stack and framework
- Entry points found
- Directory classification (core vs. supporting)
- Key dependencies identified

Wait for user confirmation before proceeding.

---

## Phase 3 — Metrics Collection

Run `tokei` to collect codebase metrics scoped to the analysis target.

```bash
bash <skill-dir>/scripts/collect_metrics.sh <target-directory> [--scope <subpath>]
```

- **Project level:** run on entire repository
- **API/Module level:** run with `--scope <module-path>` to scope metrics to the relevant directory
- **Function level:** run with `--scope` on the containing package

The script outputs:
- **stdout:** Structured JSON with language breakdown
- **stderr:** Markdown table ready for embedding in the report

Store both outputs for Phase 5.

---

## Phase 4 — Analysis

Apply analysis rules based on the scoped `{level}` and `{depth}`.

### 4.1 Project Level

* **Entrypoint inventory:** List all public interfaces (HTTP routes, RPC methods, message consumers) in a table.
* **End-to-end tracing:** Trace the path of a representative request from ingress to database/storage and back to egress.
  - Quick: prose description, 2 levels deep
  - Deep: full trace up to 5 levels, with Mermaid sequence diagram
* **Observability:** Highlight where critical logs are emitted and where key performance metrics (latency, errors) are captured.

### 4.2 API Level

* Focus on the lifecycle of a *single* entrypoint.
* **Critical dependencies:** Explicitly list all:
  - External API calls (3rd party or internal microservices)
  - Database transactions (R/W)
  - Configuration fetches (feature flags, config centers)
  - Cache reads/writes
* **Error paths:** Map how errors propagate from this endpoint.
  - Quick: list error codes returned
  - Deep: trace error wrapping chain from origin to response

### 4.3 Module Level

* Analyze a logical grouping of functionality.
* Focus on **business logic** — state changes, validation rules, decision trees.
* **Inter-module dependencies:** What does this module import? What imports this module?
  - Quick: dependency list
  - Deep: dependency graph (Mermaid flowchart)

### 4.4 Function Level

* Analyze specific functions by name.
* **Complexity:** Identify nested `if/else`, `switch` statements, loop depth.
* **Data mutation:** Track where variables are modified and types are converted.
* **Call stack:** Map the call hierarchy.
  - Quick: 2 levels deep, text only
  - Deep: 5 levels deep, Mermaid flowchart

### Visualization Rules (Deep Mode Only)

When generating Mermaid diagrams, follow **[flowchart-constraints.md](./references/flowchart-constraints.md)** strictly:

- Use descriptive camelCase node IDs
- Cap at **30 nodes per diagram** — split into sub-diagrams if exceeded
- Color external calls with `fill:#f96`
- Use diamonds for decisions, rectangles for processes
- Always escape special characters in labels

---

## Phase 5 — Report Generation

Read **[report-template.md](./references/report-template.md)** and fill in all applicable sections.

### Section Applicability by Level

| Section | Project | API | Module | Function |
|---------|:-------:|:---:|:------:|:--------:|
| Codebase Metrics | Yes | Yes (scoped) | Yes (scoped) | Yes (scoped) |
| Overview | Yes | Yes | Yes | Yes |
| Structure | Yes | No | Yes | No |
| Details | Yes | Yes | Yes | Yes |
| Data & Logic Flow | Yes | Yes | Yes | Yes |
| Visualizations | Deep only | Deep only | Deep only | Deep only |
| Dependencies | Yes | Yes | Yes | If applicable |
| Summary | Yes | Yes | Yes | Yes |

### Report File Naming

Write the report to:
```
.claude/analyses/{timestamp}_{level}_{target}.md
```

Where:
- `{timestamp}` = `YYYYMMDD` (e.g., `20260427`)
- `{level}` = `project`, `api`, `module`, or `function`
- `{target}` = kebab-case target name (e.g., `user-service`, `get-user-info`, `auth-module`)
- Example: `.claude/analyses/20260427_module_auth-service.md`

Create the `.claude/analyses/` directory if it doesn't exist.

---

## Phase 6 — Present & Review

Present the completed report to the user:

1. Show the report file path
2. Provide an executive summary (3-5 sentences covering the key findings)
3. Highlight anything surprising or noteworthy
4. Ask if the user wants to:
   - **Accept** — report is final
   - **Revise** — provide feedback for adjustments
   - **Drill deeper** — re-run at a more specific level (e.g., project → module)

If the user requests revisions, update the report file and re-present. If they request a deeper analysis, loop back to Phase 1 with the narrower scope pre-filled.

---

## Ground Rules

- **Gate each phase** — present intermediate findings, wait for user confirmation before continuing
- **Specificity over generality** — name exact patterns, files, and line numbers you find
- **Do not hallucinate** — conclusions must be based strictly on code evidence. If something is unclear, say so
- **Speed matters** — use parallel Explore agents wherever independent analysis can overlap
- **Scope to target** — at API/Module/Function level, stay focused on the target. Don't analyze the entire codebase
- **Depth is a hard limit** — Quick mode stops at 2 call levels and skips flowcharts. Deep mode traces up to 5 levels and generates all visualizations
- **30-node cap** — no Mermaid diagram should exceed 30 nodes. Split into sub-diagrams if needed
- **Track progress** — use task management tools to give the user visibility into each phase
