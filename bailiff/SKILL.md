---
name: bailiff
description: Adversarial verification of code against a spec. Reads a PRD, plan, or requirements doc, builds an independent expectation checklist *before* looking at any code, then writes and runs contract-level tests to enforce it. Always runs language-independent scans for leaked local paths, secrets/tokens, and leftover unchosen-path comments, plus language-specific quality checks. Works with blueprint/builder outputs (.claude/prds/ and .claude/plans/) or any standalone spec. Use this skill when the user wants to verify an implementation, check if code matches a spec, audit code against requirements, run acceptance tests, or asks "does this match the spec" or "did we build everything."
---

# Bailiff

Verify that an implementation actually matches what was specified. The bailiff enforces the spec — it doesn't care what the code thinks it does, it cares what the spec says it should do.

It works in two modes:

1. **With blueprint/builder artifacts** — Reads the PRD from `.claude/prds/<slug>.md` and optionally the plan from `.claude/plans/<slug>.md`. Verifies the implementation against both.
2. **Standalone** — Given any spec file and a codebase, verifies conformance independently.

Either mode can also run under **subagent transport** — invoked by another agent via the `Agent` tool instead of by a human at a REPL. See [Subagent transport](#subagent-transport) below.

## Output Location

- **Report:** `.claude/reports/<slug>-bailiff.md`
- **Re-runs after a pivot:** `.claude/reports/<slug>-bailiff-r<N>.md`. Do not silently overwrite a prior verdict — the verification trail is part of the spec history.

---

## Subagent transport

`bailiff` may be launched as a subagent from a main session that is
driving the full `blueprint → builder → bailiff → fix → bailiff` loop.
The behavior of the skill is unchanged; only the return contract
differs.

A ready-made agent wrapper ships at `.agents/bailiff.md` — install it
into your Claude Code agents directory (typically
`~/.claude/agents/bailiff.md`) and the caller can invoke this transport
via `Agent(subagent_type: "bailiff", ...)`. The wrapper is a thin shim
that invokes this skill and enforces the return contract below; the
authoritative behavior lives here.

When invoked as a subagent:

- Do all normal work. Build the expectation checklist, run static
  checks, write and run contract tests, produce the verdict, write the
  report to `.claude/reports/<slug>-bailiff-r<N>.md`, and update the
  Bailiff section of `.claude/memory/context-ledger.md` exactly as
  usual. A clean run still writes an `-rN.md` report — absence of
  findings is itself a verdict.
- **Return exactly one line** to the caller, no preamble, no summary,
  no reasoning:

      wrote <path> — <verdict> (<F failures>, <W warnings>)

  Example: `wrote .claude/reports/query-cache-bailiff-r2.md — PARTIAL (1 failure, 3 warnings)`.

- Never inline the report body, the checklist, the test output, or any
  reasoning trail into the return message. **The report on disk is the
  interface.** The main agent will read it before deciding what to fix.
- Do not use `AskUserQuestion` from inside a subagent invocation. If
  the checklist would normally prompt for confirmation (Phase 1 Step
  3), record any uncertainty as `WARN` items in the report and let the
  main agent decide. The main agent is the human's proxy; the subagent
  should not try to reach past it.
- Do not assume conversational continuity. The main agent re-launches a
  **fresh subagent** for each iteration — that freshness is what
  preserves the adversarial property. Any state you need across
  iterations must live in the report, the ledger, or the PRD.

Modes 1 and 2 above (linked / standalone) both work under this
transport — the trigger is who invoked the skill, not what artifacts
exist.

---

## Drift pre-flight (optional)

If `plumb` is available, run it before Phase 1
(`python ../plumb/scripts/drift_check.py --feature <slug>`). The
frontmatter on PRD/plan/build report tells you whether what's about to be
verified is even mutually consistent.

- **All artifacts current** → proceed normally.
- **Build report's `prd_version` is behind the live PRD's `version`** → the
  build was made against an older spec. Surface to the user: "build is N PRD
  revs stale; verify against the older spec or wait for re-build?" — do not
  invent a verdict against a moving target.
- **Plan stale but PRD/build current** → fine; the plan was just not re-emitted.
  Note it in the report Warnings.
- **WARN / UNKNOWN / LEGACY** (frontmatter missing or partial) → proceed,
  but note in the verdict that drift could not be checked precisely.

If `plumb` is not available, do the equivalent by hand: skim the PRD
date and the build report date — if the PRD is materially newer, raise the
question with the user before proceeding.

This pre-flight is the bailiff's first defense against verifying the wrong thing.

---

## The Core Principle: Spec-First, Code-Second

The bailiff must form its expectations from the spec *before* reading any implementation code. This is the single most important rule — it prevents confirmation bias, where seeing the code first makes you rationalize gaps as "probably fine."

The workflow enforces this separation strictly: Phase 1 reads only the spec. Phase 1.5 runs static checks. Phase 2 writes tests from that understanding. Only Phase 3 touches the implementation.

## Static Checks

The bailiff bundles static check scripts. These catch baseline issues that apply regardless of the spec.

### Universal (always run)

Language-independent. Run on every pass, including non-Go projects. Do **not** skip this layer.

| Check | Reference | Scripts |
|---|---|---|
| Local paths, secrets, leftover pre-thinking | [references/common_checks.md](./references/common_checks.md) | `scripts/common/check_*.js` |

Default scan is **git-tracked files plus** `.claude/`, `.agent/`, and `.agents/` (even when gitignored). Secrets and home-dir paths leak from files the current feature did not touch. `check_prethink.js` catches mechanical leftover-path comments; Phase 3 Step 4 still judges residue the regex misses.

### Language-specific

| Language | Reference | Scripts |
|---|---|---|
| Go | [references/go_checks.md](./references/go_checks.md) | `scripts/go/check_*.js` |

Each reference doc explains what the checks catch, how to run them, and how to interpret the output. If no language table row matches, still run the universal checks; only the language-specific layer is skipped.

## Performance Pitfalls Reference

Independent of language, the bailiff also carries a catalogue of
recurring performance defects — capacity misjudgments, missing
indexes, knob misalignment, unbatched hot loops — that pass compile
and CI but degrade in production. Read
[references/perf-pitfalls.md](./references/perf-pitfalls.md) at the
start of Phase 1 and use it to seed the **Performance** expectation
category. Every plan that touches a hot path (Kafka consumer,
Mongo/HBase write, Hive/Spark ETL, RPC-bound handler) should be
cross-checked against this reference.

---

## What the Bailiff Tests: The Contract Boundary

The bailiff operates at the **contract/integration test level** — it tests the same surfaces a real consumer of the feature would use. It does NOT write unit tests for internal logic.

The "contract boundary" depends on what the spec describes:

| Spec describes | Bailiff tests at |
|---|---|
| HTTP/REST endpoints | Send HTTP requests, check status codes, validate response body against the spec's schema |
| gRPC services | Call the RPC method, check the response matches the protobuf definition |
| CLI commands | Run the command, check stdout/stderr/exit codes |
| Library functions | Call the public function signature, check return values |
| Data pipelines / jobs | Check expected side effects (DB rows, messages published, files written) |

The key distinction: the bailiff tests **what comes out of the interface**, not **how the code works internally**. It doesn't care if a handler uses a database, a cache, or a magic 8-ball — it cares that the response matches the spec.

---

## What Counts as "Implementation Code" vs. "Contract Surface"

This distinction is critical because the bailiff restricts when it reads implementation code, but it needs to read enough to write tests that actually compile and run.

**Contract surface (readable in Phase 2):**
- Interface definitions: `.proto` files, OpenAPI/Swagger specs, GraphQL schemas
- Route registrations / service descriptors — just the surface: what endpoints exist, what methods are exposed
- Public type definitions and function signatures in exported packages
- Test infrastructure: test helpers, client factories, fixtures, `*_test.go`, `conftest.py`, CI config

**Implementation code (only readable in Phase 3):**
- Handler/controller bodies — the logic behind an endpoint
- Service layer / business logic
- Data access layer / repository implementations
- Internal helper functions and private methods
- Configuration parsing logic

**Example:** In a Go gRPC project, reading `service.proto` and `test_helpers.go` in Phase 2 is fine — these tell the bailiff what methods exist and how to spin up a test client. Reading `order_handler.go` to see how `CreateOrder` is implemented is NOT allowed until Phase 3.

This gives the bailiff enough to write tests that physically compile and run against real interfaces, without being influenced by the implementation's internal choices.

---

## Phase 1: Build the Expectation Checklist (Spec Only — No Code)

**Goal:** Understand what *should* exist, purely from the spec.

Do NOT read any codebase files during this phase. Only read the spec documents and the context ledger.

### Step 0: Read the Context Ledger

If `.claude/memory/context-ledger.md` exists, read it before building the checklist:
- Check the **Builder** section for acknowledged divergences — these are known deviations, not unexpected failures. Factor them into your expectations.
- Check the **Blueprint** section for design rationale — helps interpret ambiguous items in the spec.

If the file doesn't exist, skip this step.

### Step 1: Load the Spec

The user will reference a spec file — either by path or by describing what they want verified.

1. **Locate the file.** If the user gives a path, use it. If they reference a slug or feature name, check `.claude/prds/` and `.claude/plans/` for matching files.
2. **Read every spec document available** — PRD, plan, or both. The more context about intent, the better the checklist.
   - **Plan format:** Plans follow a Carmack .plan style with sections: The Problem, The Approach (with alternatives considered), The Work (phased items with progress markers), Trade-offs, Testing, and Not Doing. Extract expectations from all of these — especially Trade-offs (verify acknowledged costs are handled) and Not Doing (verify these are genuinely absent, not half-implemented).
   - **Build report:** If `.claude/reports/<slug>-build.md` exists, read it. The builder's report documents deviations from plan, tradeoffs made, and known open items — all valuable context for building the checklist.
3. Note any additional instructions the user provided (e.g., "only check the API layer").

### Step 2: Generate the Expectation Checklist

From the spec alone, produce a checklist of verifiable expectations. Each item should be:

- **Concrete and testable** — not "handles errors well" but "returns 404 when user ID does not exist"
- **Derived from the spec** — every expectation must trace back to a specific section of the spec
- **Categorized** by type:

| Category | What to check |
|---|---|
| **Functional** | Does the feature do what the spec says? Each goal, use case, and API contract becomes one or more expectations. |
| **Structural** | Are the right files, functions, and types created? Does the architecture match the technical design? |
| **Edge cases** | Are the error handling strategies from the spec implemented? What about boundary conditions implied by the constraints? |
| **Integration** | Are the dependencies wired correctly? Does data flow as described? |
| **Performance** | For every capacity/perf-sensitive item the spec names — index shapes, batch/semaphore sizing, QPS caps, jitter, partition counts, retry depth — is the implementation consistent with the numbers in the plan? See [references/perf-pitfalls.md](./references/perf-pitfalls.md) for the recurring failure modes to grep for. |
| **Omission** | Are there spec requirements with no obvious corresponding expectation? Flag these — they're the highest-risk items. |
| **Trade-offs** | Did the plan declare trade-offs or accepted costs? Verify the mitigations are in place (or that the cost was genuinely accepted, not ignored). |
| **Not Doing** | Did the plan's "Not Doing" section list deferred items? Verify they're actually absent — partially-implemented non-goals are a common source of bugs. |

Write the checklist to the report file immediately. This becomes the contract the implementation is measured against.

### Step 3: Present Checklist to User

Show the user the expectation checklist. Use `AskUserQuestion` to confirm:
- "Does this checklist cover everything you care about, or should I add/remove items?"
- Options: "Looks good, proceed" / "I have changes"

Iterate until confirmed.

---

## Phase 1.5: Run Static Checks

**Goal:** Catch baseline hygiene and language-quality issues before diving into contract tests. These apply regardless of what the spec says.

1. **Run universal checks.** Read [references/common_checks.md](./references/common_checks.md) and run `scripts/common/check_local_paths.js`, `check_secrets.js`, and `check_prethink.js` with no file arguments (default scan). This layer is mandatory.
2. **Identify the project language** from the codebase (Go, TypeScript, etc.).
3. **If a language reference exists**, read it (e.g. `references/go_checks.md` for Go). Collect changed files with `git diff --name-only` (or the user-specified scope) and run each `scripts/<lang>/check_*.js` against those files.
4. **Include static check results in the report** — dedicated "Static Checks" section before the expectation results.
5. **Promote `error` findings to Failures.** Secret literals, credentialed URLs, and private keys are Failures, not footnotes. They block a PASS verdict. `warning` / `info` stay in the Static Checks table.

A file can pass every spec-based contract test and still fail static checks (home path in source, token in `.claude/`, leftover "we considered Redis" comment, `fmt.Println` instead of `log`).

Do not copy raw secrets into the report — the scripts redact; keep them redacted.

If no language reference exists, skip only the language-specific scripts. Never skip the universal layer.

---

## Phase 2: Write Contract Tests (Spec + Contract Surface Only)

**Goal:** Turn the expectation checklist into executable tests — written from what the spec promises and the contract surface exposes, not from how the code works internally.

### Step 1: Explore Contract Surface and Test Infrastructure

Now you may read parts of the codebase, but **only** the contract surface and test infrastructure (see "What Counts as Implementation Code" above):

- **Interface definitions:** `.proto` files, OpenAPI specs, GraphQL schemas, public type signatures
- **Route/service registrations:** what endpoints exist (not what they do)
- **Test infrastructure:** test framework, runner, helpers, fixtures, conventions
- **Existing test patterns:** how tests are structured, where they live, how to run them

This gives you enough to write tests that compile, connect to real interfaces, and use the project's test conventions — without being influenced by the implementation logic.

### Step 2: Write Contract-Level Tests

For each expectation in the checklist, write one or more tests:

- **Test at the contract boundary.** Send real requests to APIs, call public functions through their exported signatures, check responses and side effects. Don't reach into internal functions or private methods.
- **Name tests after the expectation**, not the implementation. E.g., `TestCreateOrderReturns201WithOrderID` not `TestHandleCreateOrder`. The test name should read like a spec requirement.
- **Include negative cases.** If the spec says "return 404 for missing users," test that. If it says "timeout after 3s," test that. If it defines error codes, verify each one.
- **Use the project's test patterns.** If the project has a `setupTestServer()` helper, use it. If it uses table-driven tests, follow that convention. The bailiff's tests should look like they belong in the project.
- **Mark expectations that can't be auto-tested.** Some things (like "logging is present" or "config is read from X") may need manual verification — note them in the report as SKIP rather than forcing a fragile test.

Save test files following the project's test conventions.

### What happens when tests can't compile

If a test can't compile because a function name or type doesn't match what the spec implies — that's a finding, not a bug in the test. For example:

- Spec says "CreateUser endpoint" but no `CreateUser` method exists in the proto → **missing implementation** finding
- Spec says "returns UserResponse" but the proto defines `UserReply` → **naming mismatch** finding (likely a spec ambiguity)

Record these in the report. Then adapt the test to use the actual interface name (from the contract surface you read) and note the discrepancy. The goal is to get tests running so you can verify behavior, not to fail on naming alone.

---

## Phase 3: Run and Diagnose

**Goal:** Execute the tests and map failures back to spec requirements.

### Step 1: Run the Tests

Execute the test suite. Capture all output — passes, failures, and errors.

### Step 2: Read Implementation (Now Permitted)

Now, and only now, read the implementation code. For each failing test:

1. Trace the failure to the relevant source code
2. Determine the failure type:
   - **Missing implementation** — the spec requirement was not built at all
   - **Wrong behavior** — built, but does something different from what the spec says
   - **Spec ambiguity** — the spec was vague, the implementation made a reasonable choice that the test didn't anticipate
   - **Test issue** — the test's assumptions about the contract surface were wrong (e.g., used the wrong port, missed a required header)
3. For test issues — fix the test and rerun. Update the report to note what was adjusted and why.
4. For spec ambiguities — flag them as warnings, not failures. The bailiff is adversarial but fair.

### Step 3: Check for Untested Paths

With the implementation now visible, do a final scan:

- Are there code paths that exist but aren't covered by the spec? These might be bonus features or dead code — flag them as warnings.
- Are there spec requirements that passed but with suspiciously thin coverage? Strengthen those tests.
- Are there side effects the spec mentions (writes to DB, publishes events) that the tests didn't verify? Add those checks.

### Step 4: Eliminate Redundant Pre-Thinking

The plan is allowed to record alternatives. The code is not.

Cross-check the implementation against the plan's *Approach* (alternatives considered) and *Not Doing* sections. Flag as warnings (or Failures if they are live unused branches):

- Comments that recap a discarded design, justify why X was not used, or keep "the other plan" around "in case we switch"
- Commented-out functions/blocks that implement an unchosen path
- Unused helpers whose only purpose is a rejected approach
- Dead gates (`if false`, `#if 0`) wrapping leftover work

Do not "document the decision" in source. Delete the residue. The plan already has it.

---

## Phase 4: Verdict

**Goal:** Produce a clear, structured report.

Read `references/bailiff-report-template.md` and fill it in. **Set the frontmatter:**
`prd_version` and `plan_version` are the versions you actually verified — `plumb`
uses them to flag the verdict as stale once the PRD/plan move past these values.

A stale PASS verdict no longer means "the spec is met" — it means "the spec
*as of version N* was met." Make the version pin explicit.

Write the final report to `.claude/reports/<slug>-bailiff.md` (or `-r<N>.md` for re-runs).

The completed report carries:

```markdown
# Bailiff Report: <Feature Title>

**Spec:** .claude/prds/<slug>.md
**Plan:** .claude/plans/<slug>.md (if applicable)
**Date:** <today>
**Verdict:** PASS / PARTIAL / FAIL

## Summary

<1-2 sentence overall assessment>

## Static Checks

| # | File | Line | Check | Severity | Message |
|---|---|---|---|---|---|
| 1 | cmd/server.go | 42 | logging | warning | fmt.Println found — use log package |
| 2 | client/client.go | 87 | error_handling | warning | Error ignored with _ = pattern |
| 3 | cmd/server.go | 10 | local_paths | warning | Machine-local home path: /Users/***/proj |
| 4 | .claude/settings.json | 4 | secrets | error | Confidential literal (openai_key) |
| 5 | internal/store.go | 88 | prethink | warning | Redundant pre-thinking: recaps a discarded plan |

## Expectation Results

| # | Expectation | Source (spec section) | Status | Notes |
|---|---|---|---|---|
| 1 | CreateOrder returns 201 with order_id | PRD §6.2 | PASS | |
| 2 | Missing order returns 404 | PRD §7 | FAIL | Returns 500 instead |
| 3 | Timeout at 3s | PRD §4 | SKIP | Not auto-testable |
| 4 | Proto uses "CreateUser" method name | PRD §6.2 | WARN | Spec says "CreateUser", proto has "AddUser" |
| 5 | Mongo upsert on `trace_id` served by unique index | PRD §Indexes | PASS | `db.query_history_ocr_results.getIndexes()` shows `{trace_id:1}` unique |
| 6 | Consumer `sub_batch_size == yaml_batch` | Plan Phase 2 | FAIL | yaml=30, sub_batch=8 — barrier adds 4 sub-batches per handler call |

## Failures

### F1: <Title>
- **Expectation:** <what the spec says>
- **Actual:** <what happens>
- **Source:** <spec section>
- **Diagnosis:** Missing implementation / Wrong behavior / Spec ambiguity

## Warnings

- <Naming mismatches between spec and implementation>
- <Things that passed but look fragile>
- <Code paths not covered by the spec>
- <Ambiguities discovered during testing>

## Test Files

- `path/to/test_file.go` — <what it covers>

## Suggested Fixes

- <Actionable fix for each failure, if obvious>
```

### Verdict Criteria

- **PASS** — All expectations met (SKIP and WARN items are acceptable) **and** no `error`-severity static findings
- **PARTIAL** — Some expectations met, some failed, but core functionality works; **or** any `error`-severity static finding (secrets, credentialed URLs, private keys) alongside otherwise-passing expectations
- **FAIL** — Critical expectations unmet, or majority of expectations failed

Present the report to the user with a concise summary.

### Update the Context Ledger

After presenting the verdict, update the context ledger:

1. Read `.claude/memory/context-ledger.md` (create it if it doesn't exist)
2. If the Bailiff section already has content, append the old content to `.claude/memory/history/ledger-archive.md` with an `## Entry: bailiff @ {timestamp}` header
3. Overwrite the Bailiff section with:
   - One line per verified spec: `- **{slug}** ({date}, {commit}): {verdict} — {key findings}`
   - Keep last 3 verdicts maximum — drop the oldest if adding a 4th
4. Update the `Last updated:` header line
5. Keep the section within 10 content lines

See [charter/references/context-ledger-spec.md](../charter/references/context-ledger-spec.md) for the full ledger protocol.

---

## Guidelines

- **Spec is law.** The spec defines what's correct, not the code. If the code does something the spec doesn't mention, that's a warning, not a feature.
- **Chosen path only.** Code and comments describe what shipped. Unchosen paths, rejected plans, and "we could have" rationale stay in the plan, never in the code space.
- **Expectations before code.** Form your checklist before reading implementation. This is non-negotiable — it's the whole point of the adversarial approach.
- **Test at the contract boundary.** Contract-level tests through public interfaces. Don't test internals unless the spec explicitly describes them.
- **Adapt, don't fail on naming.** If the spec says "CreateUser" but the proto says "AddUser," note the discrepancy, adapt the test, and flag it. Don't let naming mismatches block the entire verification.
- **Be specific in failures.** "Doesn't work" is useless. "Returns 500 instead of 404 when order ID is missing, expected per PRD §7" is actionable.
- **Flag ambiguity honestly.** If the spec is vague and the implementation made a reasonable choice, say so. The bailiff is adversarial but fair.
- **Track progress.** Use task management tools to give the user visibility into each phase.
- **Standalone-capable.** The skill works without blueprint or builder. Any spec + any codebase = a bailiff report.
