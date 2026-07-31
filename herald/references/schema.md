# Report Schema

Herald handles four report kinds. Each has a recognisable shape — herald uses that shape to decide how to render specific signals (verdict, severity, status, diagrams). Anything outside the known sections is rendered as plain markdown without special treatment.

## Common envelope

Every report starts with a markdown H1 title and a metadata block. Herald accepts two metadata shapes:

**Shape A — `**Key:** value` lines** (bailiff, build, drift):

```markdown
# <Report Title>

**Spec:** <path>
**Date:** <YYYY-MM-DD>
**Commit:** <sha>
**Verdict:** <PASS | FAIL | …>      <!-- bailiff only -->
**Status:** <APPLIED | …>             <!-- drift only -->
```

**Shape B — leading blockquote** (analysis):

```markdown
# <Report Title>

> **Scope:** the foo + bar primitives, plus their direct call sites.
> Anything outside that surface is intentionally ignored.
>
> **Stack:** Go.  **Mode:** Module / Deep.
```

Multiple `**Key:** value` pairs may share a single quoted line, and a value may continue across continuation lines (no `**Key:**` token until a blank quote line, end of blockquote, or a new key marker). Both shapes produce the same metadata grid in the rendered header.

Any line that is `**Word:** rest of line` immediately after the H1 (until the first blank line) — or a blockquote of such lines — is captured as metadata. Order is preserved.

## Kind 1: bailiff

**Filename:** `*-bailiff.md`

**Required signals to highlight:**
- A `Verdict` field in the metadata block. Valid values: `PASS`, `FAIL`, `PARTIAL`, `BLOCKED`. Render as a coloured bracketed pill in the header — green (`--nd-success`) for PASS, red (`--nd-error`) for FAIL, yellow (`--nd-warning`) for PARTIAL/BLOCKED.

**Recognised H2 sections** (rendered with their content as-is, but with these treatments):
- **Summary** — large body text, no special treatment.
- **Static Checks** — the table inside is rendered with monospace cells; if the table contains the literal string "No findings", herald shows a green `[ CLEAN ]` pill before the table.
- **Expectation Results** — table; cells in the `Status` column get colourised (`PASS` green, `FAIL` red, `WARN` yellow, anything else neutral).
- **Warnings** — bullet list rendered with a yellow left border accent.
- **Test Files** — bullet list, monospace.
- **Suggested Fixes** — bullet list rendered with a blue (`--nd-interactive`) left border accent.

Unrecognised H2s are rendered plain.

## Kind 2: build

**Filename:** `*-build.md`

**Required signals:** none in metadata; the report's structure is the signal.

**Recognised H2 sections:**
- **Summary** — plain.
- **Motivation** — plain, slightly larger body.
- **Behavior** — bullet list; lines starting with `**path** —` get the path in monospace.
- **Deviations from Plan** — bullet list with yellow accent; the literal text `None.` renders as a green `[ NONE ]` pill instead of a list.
- **Non-goals** — bullet list, neutral grey.
- **Tradeoffs** — bullet list with yellow accent.
- **Implementation Notes** — bullet list, plain.
- **Files Changed** — bullet list; lines like `` `path` — note `` get the path styled as code.
- **Tests** — plain.
- **Open Items** — bullet list with red accent; `None.` renders as a green `[ NONE ]` pill.
- **Next Steps** — bullet list, plain.

Subheadings (H3) inside Files Changed (e.g. `### New package`) are preserved.

## Kind 3: drift

**Filename pattern:** `<branch>-<hash>-<timestamp>.md` under any `history/drift/` directory.

**Required signals:**
- A `Severity:` line somewhere in the document (typically the last paragraph of the form `## Severity: **minor**`). Values: `none`, `minor`, `major`, `critical`. Pill colours: grey / yellow / orange / red. Promote this to a pill in the header.
- A `Status:` field in the metadata block (e.g. `APPLIED`, `PENDING`, `REJECTED`). Render as a secondary pill.

**Recognised H2 sections:**
- **Structural Drift**, **Convention Drift**, **Dependency Drift**, **Interface Drift** — each is a section. Inside, H3s typically lead with a `[TAG]` like `[UPDATE]`, `[SMELL]`, `[PLANNED]`, `[INFO]`. Herald lifts that tag into a small inline pill on the H3.

| Tag       | Pill colour                |
|-----------|---------------------------|
| `[UPDATE]`  | blue (`--nd-interactive`) |
| `[SMELL]`   | red (`--nd-error`)        |
| `[PLANNED]` | green (`--nd-success`)    |
| `[INFO]`    | grey (`--nd-info`)        |

- **Severity** — already promoted; if the page has a final `## Severity:` line, herald hides that section since it's already in the header.

## Kind 4: analysis

**Filename pattern:** `YYYYMMDD_<level>_<target>.md` where `<level>` is one of `project`, `api`, `module`, `function`. Typically lives under `.claude/analyses/`. Falling back: any markdown file under a `.claude/analyses/` directory is treated as an analysis report regardless of filename.

**Required signals:** none in metadata; the report's structure is the signal. Analysis reports use blockquote-style metadata (Shape B above) — herald promotes `**Scope:**`, `**Stack:**`, `**Mode:**`, etc. to the header grid the same way bailiff metadata is shown.

**Recognised content patterns:**

- **Numbered H2 sections** (`## 1. Codebase Metrics (scoped)`, `## 2. Overview`, …). Herald renders the numbers as part of the heading; no special prefix treatment beyond the standard section border.
- **Tokei tables** with right-aligned numeric columns (using markdown `------:` separators). Rendered as plain tables — the right alignment is preserved because herald treats every column equally and the source already uses sufficient whitespace.
- **Blockquoted notes** in section bodies (e.g. `> Generated by tokei. Scoped to the analysis target directory.`). Rendered as muted text with a left border accent.
- **Mermaid diagrams** in fenced \`\`\`mermaid blocks. Herald renders each block to SVG **at build time** (mmdc → kroki → fallback) and emits a `<figure class="mermaid-figure"><img src="diagram-<sha256[:12]>.svg" alt="…">…</figure>`. The SVG file lives next to the report HTML; an identical sibling sits in `<output_dir>/<workspace>/.mermaid-cache/` so re-renders skip diagrams that haven't changed. Both `sequenceDiagram` and `flowchart`/`graph` types work.
- **ASCII box diagrams** (typically a `+----+` style sketch in a fenced code block with no language). Rendered as a plain `<pre>` so spacing survives.
- **Inline classDef styling** (e.g. `classDef ext fill:#f96,color:#000` followed by `Node:::ext`). Honoured — herald emits the mermaid source verbatim, and the runtime applies the styles.
- **Code snippets** in language-tagged fenced blocks (e.g. \`\`\`go). Rendered as `<pre><code class="lang-go">` so future syntax-highlight plugins can pick them up; today they're plain monospace on the same `--nd-surface` background as the rest of the code blocks.

Any unrecognised H2 is rendered plain with the standard section border.

**Mermaid rendering** is a build-time concern, not a per-report one — see SKILL.md "Mermaid → SVG pipeline" for the `auto` / `mmdc` / `kroki` / `none` modes. The schema itself is mode-agnostic; the same markdown produces the same diagram regardless of which renderer produced the SVG. If every renderer fails, herald inserts a `mermaid-figure--fallback` figure with the source preserved as code, so reports never silently lose information.

## Frontmatter — YAML form (optional)

If a report ships with YAML frontmatter (between `---` lines at the top), herald will parse it and merge it with the H1+metadata block. YAML keys win on conflict. This makes it easy for future skills to emit machine-friendly metadata directly:

```markdown
---
kind: bailiff
verdict: PASS
spec: .claude/prds/foo.md
commit: abc1234
---

# Bailiff Report: Foo
…
```

A `kind:` field in YAML overrides the filename-based detection. Valid values: `bailiff`, `build`, `drift`, `analysis`.

## Fallback rules

- **No metadata block found:** herald renders the title alone and skips the header strip.
- **Verdict / Severity missing on a kind that needs it:** herald renders the report without a header pill but emits a warning to stderr (does not fail).
- **Unknown H2:** rendered as plain markdown — never dropped.
- **Empty section (just a heading):** rendered with a muted `[ EMPTY ]` placeholder so the reader knows it's intentional, not truncated.
