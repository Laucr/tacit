# dev-routes.md — standard development routes

Wires the **tacit-skills** standard toolkit into the principles in [`claude.md`](./claude.md). Tells you which skill to reach for at each phase of the common workflows.

> **About skill names.** The skills below ship as the tacit-skills toolkit and get linked into Claude Code as native skills — they're invoked by name, not by filesystem path. Your environment may have additional skills installed alongside; the routes below assume the tacit-skills set is present, and the principles still apply when other skills cover the same role.

Every route assumes the principles in `claude.md` are in force: ask before coding, read the ledger inside the loop.

---

## 0. Always-on bookends

Wrap every other route.

| When | Skill | Purpose |
|---|---|---|
| First time on a repo | `warmup` | Onboard, extract conventions into `.claude/rules/`, write `.claude/memory/current.md`. |

---

## 1. Main route — blueprint → builder → bailiff → herald

Canonical SOP for non-trivial feature work. Each step reads `.claude/memory/context-ledger.md` and overwrites its own section.

```
warmup ─▶ blueprint ─▶ builder ─▶ bailiff ─▶ herald
            │              │           │          │
            └─ writes ─────┴─ reads ───┴─ reads ──┘
              .claude/memory/context-ledger.md

           (optional, when re-entering an in-flight feature)
              plumb ─▶ alignment table ─▶ builder/bailiff
```

| Step | Skill | Inputs | Outputs |
|---|---|---|---|
| 1 | `blueprint` | User intent, codebase state | `.claude/prds/<slug>.md`, `.claude/plans/<slug>.md`, ledger entry |
| 2 | `builder` | PRD + plan | Code changes, ledger entry noting any divergences |
| 3 | `bailiff` | Spec + actual code | Contract-level tests, `.claude/reports/<slug>-bailiff.md`, ledger entry |
| 4 | `herald` *(optional)* | Any markdown report above | Self-contained HTML at the configured `output_dir` |

**Pre-flight:** when picking up a feature whose PRD or plan was edited since the last build/verify, run `plumb` first. It compares the version frontmatter on the PRD, plan, build report, and bailiff verdict and flags anything stale. `builder` and `bailiff` invoke it automatically when available; running it by hand surfaces the same table without committing to a phase.

**Sub-agent transport (optional):** `bailiff` can run as a subagent launched from the main session instead of a separate REPL. Install the wrapper at `.agents/bailiff.md` into your agents directory (e.g. `~/.claude/agents/bailiff.md`) and invoke via `Agent(subagent_type: "bailiff", ...)`. The subagent reads the PRD, plan, build report, and ledger from disk; runs the skill verbatim; writes its verdict to `.claude/reports/<slug>-bailiff-r<N>.md` and its ledger entry; and returns a single line — `wrote <path> — <verdict> (<counts>)`. The reasoning trail lives in the report on disk, not in the return payload. Main agent reads the report before fixing, then re-launches a fresh subagent for the next round. Same adversarial isolation as the two-session flow, one context to drive.

**Trigger phrases:**
- "design a feature", "write a PRD", "plan how we'd add…" → `blueprint`
- "implement this", "build the plan", "execute `<plan-slug>`" → `builder`
- "verify this matches the spec", "did we build everything?" → `bailiff`
- "render this report", "make a shareable HTML" → `herald`

---

## 2. Drift route — scout → charter

Keeps codebase memory in sync after changes land.

```
(commits land on main) ─▶ scout ─▶ drift report ─▶ user reviews ─▶ charter
                                                                       │
                                                                       └─▶ updates current.md, rules/, history/
```

| Step | Skill | Purpose |
|---|---|---|
| 1 | `scout` | Detect drift since last warmup. Writes `.claude/memory/history/drift/<date>.md`. **Never modifies rules or memory.** |
| 2 | (user) | Tag each item `[UPDATE]`, `[SMELL]`, or leave it (== reject). |
| 3 | `charter` | Apply tagged decisions to `current.md` and `.claude/rules/`. The only skill that mutates stored conventions. |

**Trigger phrases:** "what's changed since last time?", "audit drift", "scan for new patterns" → `scout`; "apply the drift decisions", "sync the rules" → `charter`.

---

## 3. Requirements pivot route — pivot (+ plumb)

Triggered when requirements move while implementation is in flight. Without this route, the plan still describes the old design, the build report was made against yesterday's PRD, and the bailiff verdict no longer applies. `pivot` reconciles all three; `plumb` is the read-only sensor that surfaces what's stale before and after.

```
(spec changes mid-flight)
        │
        ▼
     plumb ─▶ alignment table ─▶ user confirms what's stale
                                              │
                                              ▼
                                          pivot ─▶ PRD bumped (in place)
                                              │      .claude/amendments/<slug>-r<N>.md
                                              │      downstream marked stale
                                              ▼
                          (return to builder/bailiff against the new PRD)
```

| Step | Skill | Purpose |
|---|---|---|
| 1 | `plumb` | Read-only. Compares version frontmatter across PRD / plan / build / bailiff. Flags STALE / WARN / LEGACY. **Never modifies files.** |
| 2 | `pivot` | Captures the pivot in `.claude/amendments/<slug>-r<N>.md` (append-only delta log), edits the PRD in place with a version bump, marks plan / build / bailiff frontmatter `status: stale`. Optionally re-emits the plan. |
| 3 | (return) | User decides whether to rebuild (`builder`) and re-verify (`bailiff`) immediately or later. `pivot` does not invoke either. |

`pivot` is **standalone**: PRDs without YAML frontmatter, with body-only `**Version:**` lines, or hand-authored markdown all work. It offers to retrofit frontmatter on the way out — opt-in, never silent.

**Trigger phrases:**
- "the requirements changed", "update the PRD", "we need to pivot", "revise the spec", "scrap that approach" → `pivot`
- "is anything stale?", "what's drifted?", "is the plan still in sync?" → `plumb`

---

## 4. Incident route — inquest (post-deploy)

Triggered when smoke / staging / production disagrees with the spec. The job is not to fix the bug — it is to figure out, fast, **which artifact lied**: the spec, the code, the verifier, or the environment.

```
(failure surfaced) ─▶ inquest ─▶ three-way diff ─▶ diagnosis
                                  (PRD / code / smoke)         │
                                                               ├─▶ code-bug   → fix code
                                                               ├─▶ spec-stale → pivot
                                                               ├─▶ spec-gap   → pivot
                                                               └─▶ environment → config / infra
```

| Step | Skill | Purpose |
|---|---|---|
| 1 | `inquest` | Anchors on the failure, snapshots current code, builds a three-way diff (PRD says ↔ code does ↔ smoke saw), classifies the failure into one of four diagnoses, writes `.claude/reports/<slug>-inquest-r<N>.md`. **Stacks; never overwrites.** |
| 2 | (route) | If diagnosis is `spec-stale` or `spec-gap`, hand off to **§3 pivot route** (`pivot`). If `code-bug`, fix and optionally re-verify (`bailiff`). If `environment`, leave the spec alone. |

`inquest` is **standalone**: works without `bailiff`, `pivot`, or `plumb`. Recommendations may reference those skills, but it never invokes them.

**Sub-agent transport (optional):** `inquest` can run as a subagent launched from the main session. Install the wrapper at `.agents/inquest.md` into your agents directory (e.g. `~/.claude/agents/inquest.md`) and invoke via `Agent(subagent_type: "inquest", ...)`. The subagent reads the PRD, plan, build report, and any prior verification/inquest reports from disk; runs the skill verbatim; writes its diagnosis to `.claude/reports/<slug>-inquest-r<N>.md` (always stacked, never overwriting); and returns a single line — `wrote <path> — <diagnosis> (<suggested next step>)`. The three-way diff and narrative live in the report on disk, not in the return payload. Main agent reads the report and decides whether to route to `pivot`, fix code, or investigate the environment.

**Trigger phrases:**
- "smoke failed", "didn't work in staging", "broken in prod", "found a bug after deploy" → `inquest`
- "verify the fix landed", "did the patch work", "confirm the change reaches X" → `inquest`

---

## 5. Architecture-doc route — code-analyze → herald

Onboarding docs, refactor maps, migration strategies.

```
code-analyze ─▶ .claude/analyses/<slug>.md ─▶ herald ─▶ shareable HTML
```

`code-analyze` does interactive scoping (project / API / module / function), quick or deep depth, framework-neutral discovery, and `tokei` metrics. `herald` renders the markdown to HTML with inline-SVG mermaid.

**Trigger phrases:** "explain the architecture", "make an onboarding doc", "map the modules" → `code-analyze`.

---

## 6. Verification-only route

When you have a spec and want to verify existing code, no new build phase.

```
(existing PRD/plan/spec) ─▶ bailiff ─▶ verdict report ─▶ herald (optional)
```

`bailiff` works on any structured spec — hand it a markdown requirements doc and it'll generate independent expectation checks before reading the code.

**Trigger phrases:** "does this match the spec?", "audit `<code>` against `<spec>`" → `bailiff`.

---

## 7. Schema-derivation route — json-to-schema

Turn a sample `.json` into a draft-07 JSON Schema with semantic annotations and shared sub-structures factored into `$ref`s.

**Trigger phrases:** "derive a schema", "what's the shape of this payload?", "generate validation rules" → `json-to-schema`.

---

## 8. Retrospective route — distill

Runs *after* the SOP loop, not inside it. Reads every `.claude/reports/*bailiff*.md` on disk and rolls individual findings into named, recurring failure modes with mechanically enforceable guardrails.

```
(bailiff reports accumulate over time) ─▶ distill ─▶ .claude/reports/bailiff-lessons-YYYY-MM-DD.md
```

`distill` is a downstream consumer, never a dependency — no other skill calls it, and it reads only bailiff reports, never audited source. Invoke periodically when the failure-mode catalog is worth refreshing.

**Trigger phrases:** "roll up the bailiff reports", "extract lessons from verifications", "what patterns keep failing?" → `distill`.

---

## Cross-skill state — `.claude/memory/` and friends

Skills coordinate through a small set of well-known directories in the target project:

```
.claude/
├── memory/
│   ├── current.md              maintained by warmup, scout, charter
│   ├── context-ledger.md       maintained by blueprint, builder, bailiff
│   └── history/
│       ├── drift/              scout outputs, charter compacts
│       ├── ledger-archive.md   charter compacts
│       └── smells-archive.md   charter compacts
├── prds/<slug>.md              blueprint writes, pivot edits in place
├── plans/<slug>.md             blueprint writes, pivot may re-emit
├── amendments/<slug>-r<N>.md   pivot's append-only delta log
└── reports/
    ├── <slug>-build.md         builder writes
    ├── <slug>-bailiff*.md      bailiff writes (re-runs become -r<N>)
    └── <slug>-inquest-r<N>.md  inquest writes (always -r<N>, stacks)
```

- **`current.md`** — last-known commit hash, structure, known smells. Read at task start.
- **`context-ledger.md`** — small (<35 lines), overwrite-based. Each skill reads before acting, overwrites its own section on completion. **Read inside the SOP loop.**
- **`history/`** — append-only archive, compacted by charter. Don't write here directly.
- **`prds/` / `plans/` / `reports/`** — versioned via YAML frontmatter (`version`, `prd_version`, `plan_version`, `last_aligned`, `status`). `plumb` reads this metadata to detect drift; `pivot` writes/updates it on a pivot.
- **`amendments/`** — append-only. One file per pivot. Never edit a prior amendment; write a new one that supersedes it if needed.

Full ledger protocol lives in the `charter` skill's references.

---

## Picking a route

```
Is the user asking for new functionality?
├── yes ──▶ blueprint → builder → bailiff (→ herald)
└── no
    │
    ├─ requirements changed mid-flight?     ──▶ pivot (with plumb to confirm staleness)
    ├─ smoke / staging / prod failure?      ──▶ inquest
    ├─ "is anything stale?" / drift status? ──▶ plumb
    ├─ verify existing code?                ──▶ bailiff
    ├─ what changed in the codebase?        ──▶ scout (→ charter)
    ├─ explain an architecture?             ──▶ code-analyze (→ herald)
    ├─ JSON shape / validation?             ──▶ json-to-schema
    ├─ roll up past verifications?          ──▶ distill
    └─ first-time repo onboarding?          ──▶ warmup
```

None of the above fits? Check the **out-of-loop utilities** list above; otherwise ask the user before building something custom or reaching for raw shell tools.
