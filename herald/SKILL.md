---
name: herald
description: Render markdown reports produced by bailiff, builder, or scout into a single self-contained HTML file styled with the nothing-design language (mirrors `@vibes/nothing-ui` tokens, no React, no build step). Use this skill whenever the user wants to share a verification report, build report, or drift report with a non-engineer audience, asks to "make this report readable / pretty / shareable", wants an HTML view of `.claude/reports/`, or says things like "render the bailiff report", "publish the build report", or "give me a viewable version of the drift report". Also trigger when the user wants a bundled index of all reports in a directory.
---

# Herald

Herald carries finished reports from the agent skills (bailiff, builder, scout) into a presentable HTML form. The source documents already exist as markdown — herald's job is to render them with the project's nothing-design language so they're legible to humans who don't live in markdown previewers, and shareable as a single file (no server, no build).

## Why herald exists

Bailiff verdicts, builder reports, and scout drift logs are dense. They're written for the developer who asked for them, but they often get forwarded — to a tech lead reviewing a PR, to a PM asking "did the migration land cleanly", to a teammate three time zones away catching up on Monday. Markdown rendered by random tools loses the structure: pass/fail tables collapse, severity loses its visual weight, frontmatter metadata becomes a blob.

Herald solves this by:

- Recognising the **shape** of each known report kind (bailiff / builder / scout) and rendering its key signals (verdict, severity, status, deviations) with appropriate visual weight.
- Producing **one standalone HTML file** with all CSS inlined — easy to email, drop into a chat, attach to a ticket. No external requests for fonts or stylesheets at render time (system font stack with the same shape as nothing-design's Space Grotesk + Fira Code pairing).
- Mirroring the **nothing-design tokens** (the same `--nd-*` custom properties as `@vibes/nothing-ui/src/tokens.css`) so the output feels like part of the same family as the vibes apps without taking a runtime dependency on the package.

## Scope: known report kinds only

Herald handles four kinds, identified by filename suffix:

| Kind     | Filename pattern                                       | Source skill |
|----------|--------------------------------------------------------|--------------|
| bailiff  | `*-bailiff.md`                                         | bailiff      |
| build    | `*-build.md`                                           | builder      |
| drift    | `<branch>-<hash>-<timestamp>.md` under `history/drift/` | scout        |
| analysis | `YYYYMMDD_<level>_<target>.md` (typically under `.claude/analyses/`) | code-analyze |

If the input doesn't match any of these, herald refuses and prints what it expected. This is a deliberate limitation — bespoke schemas are unsafe to render without knowing what the H2 sections mean. To force a kind for a file with an unconventional name, add YAML frontmatter:

```markdown
---
kind: analysis
---
# Title…
```

## Inputs and outputs

### Configuration (one-time)

Herald reads a small config at `~/.config/tacit-skills/herald.yaml`. Three keys today:

| Key           | Default       | Meaning                                                                 |
|---------------|---------------|-------------------------------------------------------------------------|
| `output_dir`  | `~/www/html`  | Where rendered HTML lives. Each workspace gets its own subfolder under this. |
| `emit_index`  | `false`       | In `--bundle` mode, also write an all-in-one `index.html` that embeds every report and lets you click between them. Off by default — most setups serve the output folder through a self-hosted dashboard or static webserver, which doesn't need a second aggregator. |
| `mermaid`     | `auto`        | How to render mermaid diagrams in analysis reports to SVG. `auto` (default) tries local `mmdc` first, then `kroki.io` over HTTP, then falls back to embedding the source as a code block. `mmdc` / `kroki` / `none` force a single path. CLI flag `--mermaid <mode>` overrides per-render. |

```yaml
output_dir: ~/www/html
emit_index: false
mermaid: auto
```

The first time the renderer runs it creates the file with defaults and tells you on stderr. To check or create the config explicitly:

```
python scripts/render.py --setup       # bundled in render.py
# or, equivalently:
python scripts/setup.py                # standalone helper
python scripts/setup.py --check        # exit 0 if config exists
python scripts/setup.py --print        # print the active config
```

If `output_dir` is `~/www/html` you can serve every workspace's reports with one `python -m http.server` rooted there — the per-workspace subdir scheme below means filenames don't collide.

### Where rendered HTML goes

Herald derives a per-workspace subfolder under `output_dir`. The workspace root is the nearest ancestor of the input that has a `.git`, `.claude/`, `go.mod`, `package.json`, `pnpm-workspace.yaml`, `pyproject.toml`, or `Cargo.toml` marker.

| Workspace state | Subfolder shape                              | Example                              |
|-----------------|----------------------------------------------|--------------------------------------|
| Git repo        | `<workspace>-<branch>-<hash4>/`              | `vibes-main-a3f2/`                   |
| No VCS info     | `<workspace>-<docker-style-name>/`           | `myproject-clever-curie/`            |

`<branch>` is slugified (slashes become dashes), `<hash4>` is the first 4 chars of the HEAD commit. The docker-style name (e.g. `clever-curie`) is **deterministic** — it's a hash of the workspace path mapped onto Docker's left/right adjective+scientist word lists, so the same workspace always gets the same name across runs. No state file needed.

So:

```
~/www/html/
├── vibes-main-a3f2/
│   ├── pet-build.html
│   └── unified-gateway-build.html
├── edu_service-master-cde1/
│   └── oss-dedup-bailiff.html
└── notes-clever-curie/        # a workspace with no git
    └── design-build.html
```

### Single report mode

```
python scripts/render.py <path/to/report.md>
```

- **Input:** one markdown file matching a known kind.
- **Output (default):** `<output_dir>/<workspace-subdir>/<basename>.html` per the scheme above.
- **Override:** pass `--out <path>` to write somewhere specific.

### Bundle mode

```
python scripts/render.py --bundle <path/to/reports-dir>            # per-report HTMLs only
python scripts/render.py --bundle <path/to/reports-dir> --index    # also emit index.html
python scripts/render.py --bundle <path/to/reports-dir> --no-index # force-skip
```

- **Input:** a directory (typically `.claude/reports/` or `.claude/memory/history/drift/`).
- **Output (default):** one `<basename>.html` per source markdown, all dropped into the same per-workspace subfolder. **No `index.html` is written by default** — most users already serve this folder through a self-hosted website or `python -m http.server`, which provides its own listing and doesn't need a separate aggregator.
- **With `--index` (or `emit_index: true` in config):** also write an all-in-one `index.html` that embeds every report and lets the reader click between them via a left-rail switcher. Useful for offline forwarding (one self-contained file).
- The workspace is derived from the **bundle directory itself**, so all reports in one bundle share one folder.

**Important — ask before emitting `index.html`.** If the user runs herald in bundle mode without specifying `--index` / `--no-index` and `emit_index` is at its default (`false`), don't second-guess it: just produce per-report HTMLs and tell them how many were written. If the user's request *implies* they want a single shareable file (e.g. "send me one HTML with everything", "make a dashboard I can email"), then either pass `--index`, or ask `Want me to also emit a single all-in-one index.html?` before adding it. Don't generate the index silently when the config says off.

## Workflow

### Step 0: Make sure herald is configured

If `~/.config/tacit-skills/herald.yaml` already exists, skip this. Otherwise (or if the user just installed herald and asks where their reports went), run `python scripts/render.py --setup`. It creates the config with defaults and prints the active `output_dir`. The renderer also auto-creates the file on first real use, so this step is mostly for explicit confirmation. (Legacy `~/.config/.herald.yaml` from earlier herald versions is migrated automatically on first run.)

### Step 1: Locate the input

The user typically points at a file (`.claude/reports/foo-bailiff.md`) or a slug (`foo`). If they give a slug:

1. Glob `.claude/reports/<slug>-*.md` — there may be several (e.g. `foo-build.md` and `foo-bailiff.md`). If more than one, ask which kind they want, or render both.
2. Drift reports live under `.claude/memory/history/drift/`; if the user says "the latest drift", pick the file with the newest timestamp in its name.

### Step 2: Identify the kind

Match the filename suffix against the table above. If nothing matches, tell the user: "Herald only renders bailiff/build/drift reports. Got `<filename>`. If this is one of those, rename it; otherwise this skill isn't the right tool."

### Step 3: Render

Run the bundled `scripts/render.py`. It does the parsing, schema mapping, and HTML emission. **Do not write your own renderer** — the script already mirrors nothing-design tokens and handles the per-kind treatments. If the script's output is wrong for a real report, fix the script and document why; don't paper over it inline.

```
python <herald>/scripts/render.py <input>            # single
python <herald>/scripts/render.py --bundle <dir>     # bundle
python <herald>/scripts/render.py <input> --out X    # custom path
```

The script prints the absolute path of the file it wrote — surface that to the user so they can open it.

### Step 4: Tell the user what was rendered and how to open it

A typical reply:

> Rendered the bailiff report to `~/www/html/edu_service-master-cde1/oss-dedup-bailiff.html`. Open it in a browser — it's a single self-contained file, no server needed.

If the user is on the remote dev box and can't open the file directly, suggest:

- `python -m http.server 0.0.0.0:8000` from `~/www/html` (their workflow already binds to 0.0.0.0 for remote access). One server now exposes every workspace's reports under predictable paths like `/<workspace>-<branch>-<hash4>/<basename>.html`.
- Copy the file to a known web-served path.

## What the rendered HTML looks like

The output mirrors the vibes nothing-design language:

- **Dark by default**, OLED-friendly background (`--nd-black: #000`), `--nd-text-primary` body, `--nd-text-display` headings.
- **Two type families:** body in Space Grotesk (with `system-ui` fallback), code/labels/data in Fira Code (with `ui-monospace` fallback). Fonts are not embedded — falling back keeps the file small and avoids external requests.
- **Three-layer hierarchy** per page: report title (display weight), section headings (heading weight), labels/metadata (Fira Code ALL CAPS).
- **Verdicts and severities** get bracketed status pills (`[ PASS ]`, `[ MAJOR ]`) using `--nd-success` / `--nd-warning` / `--nd-error` / `--nd-info`. One accent moment per page — the verdict pill in the header.
- **Tables** keep their original column structure; status cells in expectation tables get colourised by the `Status` column.
- **Mermaid diagrams** in analysis reports are rendered to SVG **at build time** and embedded as `<img src="diagram-<hash>.svg">` siblings of the HTML. No client-side JavaScript runtime is required — the rendered SVG is themed (dark surface, primary text, info-coloured edges) by whichever backend produced it. External-call class styles (`fill:#f96` etc.) defined in the diagram source are honoured. If every renderer fails, the source survives as a labelled code block so the reader at least sees what was meant to be there.
- **No gradients, no shadows, no zebra stripes, no toast popups** — flat surfaces, border separation, hover state on `--nd-surface-raised`.

### Mermaid → SVG pipeline

Diagrams are rendered to SVG at build time via a fallback chain. The mode is set in `~/.config/tacit-skills/herald.yaml` (`mermaid: <mode>`) and overridden per-render with `--mermaid <mode>`.

| Mode    | Tries                                  | Network? | Local deps                                          | When to use                                                  |
|---------|----------------------------------------|----------|-----------------------------------------------------|--------------------------------------------------------------|
| `auto`  | mmdc → kroki → fallback `<pre>`        | only if mmdc fails | none (degrades gracefully)              | **Default.** Best result available without forcing setup.    |
| `mmdc`  | local `@mermaid-js/mermaid-cli` only   | no       | Node ≥18, Chromium shared libs (see "mmdc setup") | Best fidelity + fully offline, when the toolchain works.     |
| `kroki` | https://kroki.io/ JSON endpoint        | yes      | none                                                | Internet is available; local mmdc isn't (or you don't want to install Chromium libs). |
| `none`  | nothing                                | no       | none                                                | Dashboard already renders mermaid server-side, or you don't care about diagrams. |

**Caching.** Each diagram source is hashed (sha256, first 12 hex chars) and cached at `<output_dir>/<workspace>/.mermaid-cache/diagram-<hash>.svg`. Re-renders skip diagrams that haven't changed — the second run of the same report is instant. The cache is mirrored into the workspace folder as `diagram-<hash>.svg` so `<img>` tags in the rendered HTML resolve directly without serving a hidden directory.

**mmdc setup.** `mmdc` runs through `npx --yes -p @mermaid-js/mermaid-cli mmdc`, which downloads on first use. Under the hood it spawns Chromium via Puppeteer, which needs system shared libraries. On Debian/Ubuntu:

```bash
apt-get install -y \
  libatk-bridge2.0-0 libatk1.0-0 libcups2 libdrm2 libgbm1 libnspr4 libnss3 \
  libpangocairo-1.0-0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
  libxkbcommon0 libxshmfence1 libasound2
```

When mmdc fails (missing libs, sandbox restrictions, etc.), `auto` mode falls through to kroki silently and prints a one-line stderr note.

**Failure mode.** When every renderer fails, herald inserts a `<figure class="mermaid-figure mermaid-figure--fallback">` containing a `[ DIAGRAM SOURCE — RENDER UNAVAILABLE ]` caption and the original mermaid source as a code block. The reader still sees structure and labels; the report doesn't silently lose information.

For the full schema (frontmatter fields, expected H2 sections, fallback rules), read [references/schema.md](./references/schema.md). For the rationale and constraints behind the styling, read [references/design.md](./references/design.md).

## Boundaries

- Herald is **read-only on the source markdown.** Never edit a bailiff/builder/scout report to make it render better — fix the renderer instead.
- Herald **does not interpret report content.** A failing bailiff verdict stays failing; herald just shows it more loudly. If the user wants a summary or recommendation, that's a different skill.
- Herald **does not embed fonts.** Doing so would 5-10x the file size for marginal fidelity gain. The system fallback (Space Grotesk → DM Sans → system-ui; Fira Code → JetBrains Mono → ui-monospace) holds the layout.
- Herald **does not fetch remote assets** for the rendered HTML itself — no remote fonts, no remote JS, no remote CSS. The only outbound network call is at *build time* in `auto`/`kroki` mermaid modes, when herald POSTs diagram source to kroki.io to receive an SVG. The rendered HTML and its sibling SVG files are openable offline forever after that.
