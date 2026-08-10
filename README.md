# tacit-skills

[English](./README.md) | [简体中文](./README-CN.md)

A cohesive toolkit of AI-powered skills—and their companion app bundles—for taking software from first inspection through design, implementation, verification, and durable project memory.

## Overview

This repository contains **17 independent skills** designed to streamline software development workflows.

### Onboarding & Maintenance
- **[warmup](./warmup/SKILL.md)** — Codebase onboarding. Explore repo structure, extract Go conventions, and distill them into a Claude-compatible development rule file.
- **[scout](./scout/SKILL.md)** — Codebase drift detection. Compare git history and Go sources against stored conventions to flag structural changes, convention deviations, and interface modifications.
- **[charter](./charter/SKILL.md)** — Memory sync. Apply approved scout drift reports to update conventions, rules, and project memory. Includes history compaction.

### Design & Implementation
- **[blueprint](./blueprint/SKILL.md)** — Pre-implementation design workflow. Explore codebase, draft PRDs, create implementation plans—design-first approach before coding.
- **[builder](./builder/SKILL.md)** — Build features from specifications. Takes PRDs or implementation plans and produces working code.
- **[pivot](./pivot/SKILL.md)** — Handle a mid-flight requirements pivot. Captures the change in `.claude/amendments/<slug>-r<N>.md`, edits the PRD in place with a version bump, and marks the existing plan / build report / bailiff verdict as stale. The "fifth verb" the SOP was missing.
- **[code-analyze](./code-analyze/SKILL.md)** — Architectural code analysis tool with interactive scoping (project/API/module/function levels), quick/deep depth modes, framework-neutral discovery, and `tokei`-powered metrics. Reports output to `.claude/analyses/`. **Prerequisite:** `tokei` ([install](https://github.com/XAMPPRocky/tokei#installation)).

### Verification
- **[bailiff](./bailiff/SKILL.md)** — Spec-driven verification with contract-level testing. Validates implementations against specifications and runs Go code quality checks.
- **[plumb](./plumb/SKILL.md)** — Compare versions on PRD / plan / build / bailiff artifacts and report which features have stale plans, builds, or verdicts. Read-only sensor — never modifies files. Auto-invoked by builder and bailiff as a pre-flight check.
- **[smoke-client](./smoke-client/SKILL.md)** — Scaffold a standalone Go smoke-test client for one in-process function or live HTTP endpoint. Replays JSONL inputs without booting the surrounding service and writes stable parsed, results, skipped, and failures JSONL artifacts; dry-run mode performs decoding only and makes no network calls.
- **[inquest](./inquest/SKILL.md)** — Post-verdict / post-deploy investigation with two modes: **smoke** (three-way diff PRD ↔ code ↔ smoke, diagnose whether the failure is a code bug, spec gap, spec-stale, or environment issue) and **triage** (walk a bailiff report's findings, independently verify each, fix the real ones in place — scoped to files the finding names — and flip the bailiff report's status to reflect what actually happened). Never invokes other skills.

### After-action retrospective
- **[distill](./distill/SKILL.md)** — Periodic cross-repo meta-review. Reads every bailiff report on disk and abstracts individual findings into named, recurring failure modes with mechanically enforceable guardrails, saved as a dated `bailiff-lessons-YYYY-MM-DD.md`. Runs *after* the SOP loop, never inside it — a downstream consumer of other skills' outputs, not a dependency. Reads only bailiff reports, never audited source. No other skill should call distill; distill may reference other skills' catalogues (e.g., bailiff's `references/perf-pitfalls.md`) to preserve stable identifiers across digests.

### Reporting
- **[herald](./herald/SKILL.md)** — Render bailiff/builder/scout markdown reports into a single self-contained HTML file styled with the nothing-design language. Mirrors `@vibes/nothing-ui` tokens via inline CSS — no React, no build step, no remote fetches. Single-report and multi-report bundle modes.

### Utilities
- **[json-to-schema](./json-to-schema/SKILL.md)** — Convert a sample `.json` file into a draft-07 JSON Schema definition. Infers types, factors shared sub-structures into `$ref` definitions, and adds semantic annotations (datetime, HTML, signed URLs). Includes a validation script.

### Long-term Memory: the Honcho suite

The three Honcho skills form a complete memory loop rather than a bag of isolated commands: administer the service, save durable context, and bring the right context back into later work.

- **[honcho-manage](./honcho-manage/SKILL.md)** — Operate the self-hosted Honcho sidecar end to end: bootstrap and build the Docker Compose stack, wait for service readiness, inspect health and session details, switch scopes, and safely clean up memories across every API page.
- **[honcho-remember](./honcho-remember/SKILL.md)** — Turn user preferences, project facts, decisions, and standing instructions into validated, atomic observations stored in the active session.
- **[honcho-recall](./honcho-recall/SKILL.md)** — Bring stored knowledge back with recent-memory listing or semantic search, consistently scoped to the active session so project contexts do not bleed into one another.

For a fully self-hosted stack, these skills work especially well with **[Laucr/honcho](https://github.com/Laucr/honcho)**, a Honcho fork that includes a self-hosted embedding service. The pairing keeps memory storage and embedding inference under your control while preserving the same manage → remember → recall workflow.

Together with **Memboard** in [`.pkg/memboard`](./.pkg/memboard/), the suite provides both agent-native workflows and a human-friendly web control surface for browsing, searching, and deleting stored memories.

## Quick Start Workflow

The typical development workflow is:

```
0. warmup       → Onboard to codebase, extract conventions
1. blueprint    → Generate PRD & implementation plan
2. builder      → Implement from spec   (plumb pre-flight)
3. bailiff      → Verify implementation matches spec   (plumb pre-flight)
4. scout        → Detect drift from conventions (after changes land)
5. charter      → Apply approved drift updates to memory (companion to scout)
6. code-analyze → Document architecture (optional)
7. herald       → Render any of the above reports into shareable HTML (optional)
```

After the loop, periodically:

```
*. distill      → Roll up every bailiff report on disk into a dated
                  lessons file. Retrospective only — runs downstream of
                  the SOP, never inside it.
```

When the spec moves while implementation is in flight:

```
*. pivot        → Bump the PRD, log the delta, mark plan/build/bailiff stale
*. plumb        → Read-only sensor: which features have stale artifacts?
```

When the real world disagrees with the spec, or bailiff leaves open findings:

```
*. smoke-client → Scaffold a JSONL-driven harness for one function or HTTP
                  endpoint; dry-run validates inputs, online runs produce
                  parsed/results/skipped/failures evidence.
*. inquest      → smoke mode: three-way diff (PRD says ↔ code does ↔ smoke saw)
                  → diagnose code-bug vs spec-stale vs spec-gap vs environment.
                  triage mode: verify each bailiff finding, fix the real ones in
                  place (scoped to named files), reject the rest, flip the
                  bailiff report's status. Never runs pivot or bailiff itself.
```

Blueprint, builder, and bailiff exchange context automatically via the **context ledger** — blueprint decisions inform builder, builder divergences inform bailiff, and bailiff verdicts feed back into the next blueprint cycle. The frontmatter on each artifact (PRD `version`, plan `prd_version`, build/bailiff `prd_version` + `plan_version`) is what `plumb` and `pivot` read to keep the chain honest as requirements evolve.

For long-term memory:

```
1. honcho-manage   → Setup and administer memory sidecar
2. honcho-remember → Save preferences, decisions, context
3. honcho-recall   → Retrieve stored knowledge
```

The suite resolves its Honcho home from `HONCHO_HOME` first, then the current project (a Compose root or nearest `.claude/honcho/`), and finally Honcho's global `~/.honcho/` convention. This makes one installation useful both for globally shared preferences and for isolated project sessions.

## Companion bundles (`.pkg`)

Skills are the agent-facing interface; `.pkg/` contains the optional software that makes selected skills feel like a complete product. These bundles are deliberately kept under a hidden top-level directory so coding-agent skill loaders do not mistake them for standalone skills.

### Memboard

**[Memboard](./.pkg/memboard/)** is the web companion to the Honcho memory suite. It turns the same Honcho v3 API used by the skills into a compact control panel where a person can:

- see service health and memory counts;
- browse all memories or filter them by session;
- run semantic searches;
- delete an individual memory or wipe a session with confirmation; and
- use the UI locally through Vite or ship it as a small containerized bundle.

Memboard is a standalone Vite + React application. By default its development server proxies `/api` to Honcho at `http://localhost:8787`; workspace, observer, observed peer, base path, and API location remain configurable through the documented `VITE_*` and `HONCHO_BASE_URL` environment variables in the app source.

## Cross-Skill Memory

Skills share context through files in `.claude/memory/` (created in target projects):

```
.claude/memory/
├── current.md              # Codebase state snapshot (commit, structure, known smells)
├── context-ledger.md       # Cross-skill context exchange (~35 lines, overwrite-based)
└── history/
    ├── drift/              # Scout drift reports (compacted by charter)
    ├── ledger-archive.md   # Archived ledger entries
    └── smells-archive.md   # Archived smell entries
```

- **`current.md`** — maintained by scout/charter. Tracks the last-known commit hash and codebase state.
- **`context-ledger.md`** — maintained by blueprint, builder, bailiff, and inquest. Each skill overwrites its own section on completion (never appends), keeping the file small. Scout reads it to distinguish planned changes from drift.
- **`history/`** — charter compacts old drift reports and ledger archives to prevent unbounded growth.

Full protocol: [charter/references/context-ledger-spec.md](./charter/references/context-ledger-spec.md)

## Installation

Wire this repo's skills into one or more coding-CLI vendor directories with the bundled installer:

```bash
bash .scripts/install.sh                                 # interactive first-install / sync
bash .scripts/install.sh --dry-run                       # preview actions, change nothing
bash .scripts/install.sh --yes --wired claude --groups core  # non-interactive
bash .scripts/install.sh --enable-group vec-memory       # add long-term memory skills later
bash .scripts/install.sh --check                         # exit 0 if a rerun would be a no-op
bash .scripts/install.sh --uninstall                     # remove everything and delete config
```

By default the installer **symlinks** each skill dir into `<vendor>/skills/`, so `git pull` in this repo propagates skill *content* changes to every wired vendor instantly. Reruns of `install.sh` are for changes to the skill *set* (a skill added/removed upstream) and for re-emitting the policy and agent-wrapper files. Use `--mode copy` on filesystems without symlink support — in copy mode a rerun also updates the skill content itself, so the installed version tracked in `installer.yaml` matters.

`--check` reports what a rerun would change: dangling or missing symlinks in symlink mode; version drift in copy mode; and policy / agent conflicts either way. Exit 0 = in sync (nothing to do), non-zero = a rerun would resolve something.

Alongside skills, the installer copies two kinds of file:

- **Policy files** (`CLAUDE.md`, `dev-routes.md`) into each vendor's `policy_dir`. The variant is picked by enabled group — `.policy/core/` for core-only, `.policy/vec-memory/` when the `vec-memory` group is on. Foreign files (no `<!-- tacit-skills policy v1` header) are refused unless you pass `--force`, which moves them to `.tacit-backup` before overwriting.
- **Agent wrappers** (`.agents/*.md`) into each vendor's `agents_dir`. These let a caller invoke a skill under **subagent transport** — e.g. `Agent(subagent_type: "bailiff", ...)` — with a one-line return contract; the reasoning trail lives in the on-disk report. Skip with `--no-agents`, override the path with `--agents-dir NAME=PATH`, or point one vendor to `~/.claude/agents/` if that's where your CLI looks.

Known vendor defaults:

| Vendor          | Skills dir                    | Policy dir           | Agents dir                   |
|-----------------|-------------------------------|----------------------|------------------------------|
| claude | `~/.claude/skills`   | `~/.claude` | `~/.claude/agents`  |
| codex       | `~/.codex/skills`         | `~/.codex`       | `~/.codex/agents`        |

Add custom vendors interactively (`[a]` at the prompt) or via `--add-vendor NAME=PATH` (repeatable). Set a policy dir with `--policy-dir NAME=PATH` and an agents dir with `--agents-dir NAME=PATH` (empty PATH = skip that class for that vendor). See `bash .scripts/install.sh --help` for the full flag set.

Every install/upgrade/uninstall action appends a JSON-Lines record to `~/.local/state/tacit-skills/install.log`.

### Cutting a release

Maintainers cut a version tag with:

```bash
bash .scripts/release.sh patch          # v0.3.0 -> v0.3.1 (annotated tag, no push)
bash .scripts/release.sh minor --push   # tag and push to origin
bash .scripts/release.sh --dry-run patch
```

Preflight refuses to tag on a dirty tree or an already-tagged HEAD unless `--force` is passed. No CHANGELOG.md is maintained; the annotated tag carries `git log --oneline` between releases.

### Editing policy files

`.policy/` holds two variants of the standard policy files:

- `.policy/core/` — the base narrative, no long-term-memory references.
- `.policy/vec-memory/` — the same narrative with long-term-memory rules and route entries woven in. Currently backed by the `honcho-*` skill set; the `vec-memory` name is deliberately capability-scoped so the underlying tool can change without a rename.

The installer picks the variant based on the enabled group set (`--groups core,vec-memory` → `vec-memory`, otherwise `core`). Both files must be kept in step for the shared narrative; the divergences are the point. There is no lint step — a `diff` between the two `.md` files is the review surface.

Legacy: `--groups honcho` and `--enable-group honcho` still work and silently alias to `vec-memory`.

## Configuration

Skill-local config files (the per-skill YAML/JSON a Setup stage writes) live under a single XDG-style root:

```
~/.config/tacit-skills/<skill-name>.yaml
```

Currently registered:
- `~/.config/tacit-skills/installer.yaml` — installer state (wired vendors, enabled groups, last-installed version). Written by `.scripts/install.sh`; safe to hand-edit if you follow the flat schema (see the file's `# tacit-skills installer.yaml v1` header for the version marker).
- `~/.config/tacit-skills/herald.yaml` — herald output/index/mermaid config (auto-created on first run; legacy `~/.config/.herald.yaml` is migrated automatically).

Resolution order for runtime values:
1. Environment variables
2. `~/.config/tacit-skills/<skill-name>.yaml` (skill-local config)
3. `.claude/settings.json` (project-level harness settings)
4. `~/.claude/settings.json` (user-level harness settings)

> Honcho skills (`honcho-manage`, `honcho-recall`, `honcho-remember`) intentionally use `~/.honcho/` — that path is Honcho's own product convention, not a tacit-skills config and is not relocated.

### Migrating from older layouts

If you upgraded from a version of tacit-skills that wrote configs elsewhere (e.g. `~/.config/.herald.yaml`), run the bundled migrator once:

```bash
python .scripts/migrate-configs.py            # perform the migration
python .scripts/migrate-configs.py --dry-run  # preview what would move
python .scripts/migrate-configs.py --check    # exit 0 if everything is already migrated
```

The script is **idempotent** — re-running it after a clean migration is a no-op. If both a legacy file and a new file exist for the same skill, the migrator refuses to overwrite and prints both paths so you can resolve the conflict by hand. Per-skill scripts (e.g. `herald/scripts/render.py`) also perform the same migration on first run, so the standalone migrator is a convenience for "do everything at once" / batch upgrades.

To register a new legacy mapping, append a tuple to `LEGACY_MAPPINGS` in `.scripts/migrate-configs.py`.

## Skill authoring conventions

Constraints every new skill must follow if it needs to **persist anything in the user's filesystem**:

1. **One file per skill, under the unified root.** Write to exactly one path: `~/.config/tacit-skills/<skill-name>.<ext>` (use `.yaml` for structured config, `.json` only if you genuinely need JSON, `.env` for shell-sourced env files). Do **not** invent per-skill subdirectories, and do **not** write into the skill's own directory inside the repo — repo dirs are read-only artifacts that get overwritten on update.
2. **Never write to `$CWD`, `~/.claude/`, or arbitrary `~/<dotdir>/` locations.** The only sanctioned exception is when a skill wraps a third-party product that owns its own config root (e.g. Honcho's `~/.honcho/`); in that case, document it explicitly in `SKILL.md` and the README's "Configuration" section, and do **not** mirror it under `tacit-skills/`.
3. **Auto-create with sensible defaults.** On first run, if `~/.config/tacit-skills/<skill>.<ext>` is missing, write it with documented defaults (parent dir created via `mkdir -p`) and tell the user on stderr where it landed. The user must never be left guessing where their config lives.
4. **Keep parsing dependency-free.** Prefer a tiny `key: value` YAML subset parsed with stdlib (see `herald/scripts/render.py:load_config`) over PyYAML; reach for a real YAML parser only if the schema genuinely needs nesting/lists. JSON is fine via `json.stdlib`.
5. **Provide a migration path when you change the location.** If you rename or move a config file in a later version, register the old → new mapping in `.scripts/migrate-configs.py` (`LEGACY_MAPPINGS`), and add a one-time auto-migration in the skill's own scripts (mirror the `LEGACY_CONFIG_PATH` + `ensure_config()` pattern in `herald/scripts/render.py`). Never silently break existing users.
6. **Document the path.** Every skill that persists config must mention the exact path in its `SKILL.md` Setup section, and the README's "Configuration / Currently registered" list must be updated in the same change.
7. **No secrets in the config file.** Tokens, passwords, API keys, etc. belong in env vars (or a user-managed `auth.env_file` reference); the YAML/JSON in `~/.config/tacit-skills/` should be safe to back up to a personal git repo without leaking credentials.

A skill that does not need to persist anything (most of them — `pivot`, `bailiff`, `blueprint`, `builder`, `charter`, `code-analyze`, `distill`, `inquest`, `json-to-schema`, `plumb`, `scout`, `smoke-client`, `warmup`) should not create any file under `~/.config/tacit-skills/`. Stay stateless when you can.

## Repository layout

Each skill is one directory at the repo root containing `SKILL.md` plus optional `scripts/` and `references/` subdirectories. **The Claude Code skill loader treats every non-dotfile top-level directory as a skill candidate**, so any repo-wide tooling lives under a hidden directory:

- `.scripts/` — repo-wide tools (`install.sh`, `release.sh`, `migrate-configs.py`, `test-install.sh`)
- `.policy/` — policy variants (`core/`, `vec-memory/`) rendered into each vendor's `policy_dir` by the installer
- `.agents/` — agent wrappers (`bailiff.md`, `inquest.md`) rendered into each vendor's `agents_dir` by the installer
- `.pkg/` — optional companion applications and distributable bundles attached to specific skill suites; currently includes the Honcho suite's Memboard web UI
- `.claude/` — harness state and permissions

Don't add new non-dot top-level directories unless they're a real skill with a `SKILL.md`.
