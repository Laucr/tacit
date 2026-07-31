#!/usr/bin/env python3
"""
herald/scripts/render.py

Render bailiff/builder/scout/code-analyze markdown reports into a single
self-contained HTML file styled with the nothing-design language. Pure stdlib —
no third-party deps, no build step. Mermaid diagrams (used by analysis reports)
are rendered to SVG at build time via mmdc → kroki → fallback, then embedded
as `<img src="diagram-<hash>.svg">` siblings of the rendered HTML.

Usage:
    python render.py --setup                       # check or create ~/.config/tacit-skills/herald.yaml
    python render.py <input.md>                    # single report
    python render.py <input.md> --out <path>       # custom output path
    python render.py <input.md> --mermaid <mode>   # override mermaid delivery
    python render.py --bundle <reports-dir>        # per-report HTMLs only (default)
    python render.py --bundle <dir> --index        # also emit all-in-one index.html
    python render.py --bundle <dir> --no-index     # force-skip index.html (override config)

Output paths are derived from the configured `output_dir` (default: ~/www/html):

    <output_dir>/<workspace>-<branch>-<hash4>/<basename>.html   # in a git repo
    <output_dir>/<workspace>-<docker-name>/<basename>.html      # no VCS info

In bundle mode, the all-in-one `index.html` switcher is OFF by default — most
setups serve the output folder via a self-hosted dashboard / static webserver,
which doesn't need a separate aggregator file. Toggle with `emit_index` in the
config file or with `--index` / `--no-index`.

Mermaid modes (config key `mermaid`, CLI flag `--mermaid`):

    auto  — try local mmdc, then kroki.io HTTP, then leave the source as code.
            (default)
    mmdc  — local @mermaid-js/mermaid-cli only.
    kroki — POST to https://kroki.io/mermaid/svg.
    none  — render mermaid blocks as code listings.

Rendered SVGs are cached under <workspace_output>/.mermaid-cache/ and mirrored
to the workspace folder as `diagram-<sha256[:12]>.svg` siblings of each HTML.

The schema and per-kind treatments are documented in ../references/schema.md.
The design choices (token mirroring, font fallbacks) are in ../references/design.md.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


# ─── Kind detection ──────────────────────────────────────────────────────────

KIND_BAILIFF = "bailiff"
KIND_BUILD = "build"
KIND_DRIFT = "drift"
KIND_ANALYSIS = "analysis"

DRIFT_FILENAME_RE = re.compile(r"^[\w.\-]+-[0-9a-f]{7,}-\d{8}T\d{4}\.md$")
# Analysis filename: YYYYMMDD_<level>_<target>.md (code-analyze convention)
ANALYSIS_FILENAME_RE = re.compile(
    r"^\d{8}_(project|api|module|function)_[\w.\-]+\.md$",
    re.IGNORECASE,
)


def detect_kind(path: Path, yaml_kind: str | None = None) -> str | None:
    """Identify the report kind. YAML frontmatter beats filename detection."""
    if yaml_kind:
        k = yaml_kind.strip().lower()
        if k in {KIND_BAILIFF, KIND_BUILD, KIND_DRIFT, KIND_ANALYSIS}:
            return k

    name = path.name
    if name.endswith("-bailiff.md"):
        return KIND_BAILIFF
    if name.endswith("-build.md"):
        return KIND_BUILD
    # Analysis: <YYYYMMDD>_<level>_<target>.md, optionally inside .claude/analyses/
    if ANALYSIS_FILENAME_RE.match(name):
        return KIND_ANALYSIS
    parts_norm = str(path.parent).replace("\\", "/")
    if "/.claude/analyses" in parts_norm or parts_norm.endswith("/.claude/analyses"):
        return KIND_ANALYSIS
    # Drift: <branch>-<hash>-<timestamp>.md, optionally inside a history/drift/ tree
    if DRIFT_FILENAME_RE.match(name) and "history/drift" in parts_norm:
        return KIND_DRIFT
    if DRIFT_FILENAME_RE.match(name):
        # Filename matches but path doesn't include history/drift — still likely a drift report
        return KIND_DRIFT
    return None


# ─── Markdown parsing ────────────────────────────────────────────────────────

@dataclass
class Block:
    """A coarse block of the document. Type values:
    h1 / h2 / h3 / h4 / paragraph / list / olist / table / code / hr / metadata / empty
    """
    kind: str
    text: str = ""              # for headings, paragraphs, code
    items: list[str] = field(default_factory=list)  # for lists (raw md lines)
    rows: list[list[str]] = field(default_factory=list)  # for tables
    headers: list[str] = field(default_factory=list)     # for tables
    lang: str = ""              # for code fences
    extras: dict = field(default_factory=dict)


@dataclass
class Report:
    title: str
    metadata: list[tuple[str, str]]   # ordered (key, value)
    blocks: list[Block]
    kind: str | None
    yaml: dict
    severity: str | None = None       # for drift
    verdict: str | None = None        # for bailiff
    status: str | None = None         # for drift / generic

    @property
    def uses_mermaid(self) -> bool:
        return any(b.kind == "mermaid" for b in self.blocks)


def split_yaml_frontmatter(text: str) -> tuple[dict, str]:
    """If the document opens with --- ... ---, parse a tiny key:value YAML subset."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    yaml_block = lines[1:end]
    body = "\n".join(lines[end + 1 :])
    fm: dict = {}
    for ln in yaml_block:
        if ":" in ln:
            k, v = ln.split(":", 1)
            fm[k.strip()] = v.strip().strip("\"'")
    return fm, body


METADATA_RE = re.compile(r"^\*\*([^*:]+?):\*\*\s*(.*)$")
# Analysis reports often place their metadata inside a leading blockquote:
#   > **Scope:** the eight gray-control keys ...
#   > **Stack:** Go.  **Mode:** Module / Deep.
# Match a single `**Key:** value` pair (we'll iterate to capture multi-pair lines).
KV_INLINE_RE = re.compile(r"\*\*([^*:]+?):\*\*\s*([^*]*?)(?=(?:\s*\*\*[^*:]+?:\*\*)|\s*$)")


def parse_markdown(text: str) -> tuple[str, list[tuple[str, str]], list[Block]]:
    """Parse a markdown report into (title, metadata, blocks)."""
    lines = text.splitlines()
    i = 0

    # Skip leading blank lines
    while i < len(lines) and not lines[i].strip():
        i += 1

    title = ""
    if i < len(lines) and lines[i].startswith("# "):
        title = lines[i][2:].strip()
        i += 1

    # Skip blank lines after title
    while i < len(lines) and not lines[i].strip():
        i += 1

    # Metadata block. Two shapes are accepted before the first content block:
    #
    #   1. Plain `**Key:** value` lines (bailiff/build/drift)
    #   2. A leading blockquote of `> **Key:** value` lines, possibly with
    #      multiple key/value pairs per line (analysis reports use this).
    metadata: list[tuple[str, str]] = []

    # Shape 2: blockquote-style metadata. Values may continue onto multiple
    # quoted lines until a blank-quote line, end of blockquote, or the next
    # `**Key:**` token. We collect everything that follows a key marker into
    # the same value so e.g. a multi-line Scope: paragraph survives intact.
    if i < len(lines) and lines[i].lstrip().startswith(">"):
        j = i
        captured: list[tuple[str, str]] = []
        active_key: str | None = None
        active_val_parts: list[str] = []

        def _flush() -> None:
            if active_key is not None:
                captured.append((active_key, " ".join(p.strip() for p in active_val_parts).strip().rstrip(".")))

        well_formed = True
        while j < len(lines) and lines[j].lstrip().startswith(">"):
            inner = lines[j].lstrip()[1:].strip()
            if not inner:
                # Blank quote line: end the current value, but keep scanning —
                # there may be more key/value pairs below.
                _flush()
                active_key = None
                active_val_parts = []
                j += 1
                continue
            pairs = list(KV_INLINE_RE.finditer(inner))
            if pairs:
                # New key(s) on this line. Multiple pairs can share a line:
                # "**Stack:** Go.  **Mode:** Module / Deep."
                # Flush whatever we were accumulating before starting fresh.
                if active_key is not None:
                    _flush()
                    active_key = None
                    active_val_parts = []
                if len(pairs) == 1:
                    active_key = pairs[0].group(1).strip()
                    active_val_parts = [pairs[0].group(2)]
                else:
                    # Each pair is complete on this line; commit them all.
                    for m in pairs:
                        captured.append((m.group(1).strip(), m.group(2).strip().rstrip(".")))
                    active_key = None
                    active_val_parts = []
                j += 1
                continue
            # Plain prose inside the blockquote.
            if active_key is not None:
                active_val_parts.append(inner)
                j += 1
                continue
            # Prose with no preceding key — this isn't a metadata block at all.
            well_formed = False
            break
        _flush()

        if well_formed and captured:
            metadata.extend(captured)
            i = j
            # Skip blank lines after the blockquote
            while i < len(lines) and not lines[i].strip():
                i += 1

    # Shape 1: consecutive `**Key:** value` lines until a blank line.
    while i < len(lines) and lines[i].strip():
        m = METADATA_RE.match(lines[i].strip())
        if not m:
            break
        metadata.append((m.group(1).strip(), m.group(2).strip()))
        i += 1

    blocks: list[Block] = []
    while i < len(lines):
        ln = lines[i]
        stripped = ln.strip()

        # Blank line — separator
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if stripped in {"---", "***", "___"}:
            blocks.append(Block("hr"))
            i += 1
            continue

        # Code fence — `mermaid` becomes a dedicated block kind so it can
        # render through the mermaid runtime instead of as a code listing.
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            buf: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            if i < len(lines):
                i += 1  # consume closing fence
            kind_block = "mermaid" if lang.lower() == "mermaid" else "code"
            blocks.append(Block(kind_block, text="\n".join(buf), lang=lang))
            continue

        # Headings
        if stripped.startswith("#### "):
            blocks.append(Block("h4", text=stripped[5:].strip()))
            i += 1
            continue
        if stripped.startswith("### "):
            blocks.append(Block("h3", text=stripped[4:].strip()))
            i += 1
            continue
        if stripped.startswith("## "):
            blocks.append(Block("h2", text=stripped[3:].strip()))
            i += 1
            continue
        if stripped.startswith("# "):
            blocks.append(Block("h1", text=stripped[2:].strip()))
            i += 1
            continue

        # Tables — rough GFM detection: a line with `|` followed by a separator line
        if "|" in ln and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)+\|?\s*$", lines[i + 1]):
            headers = [c.strip() for c in _split_table_row(ln)]
            i += 2  # header + separator
            rows: list[list[str]] = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append([c.strip() for c in _split_table_row(lines[i])])
                i += 1
            blocks.append(Block("table", headers=headers, rows=rows))
            continue

        # Bullet list
        if re.match(r"^\s*[-*]\s+", ln):
            items: list[str] = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]))
                i += 1
                # support 1-line continuations indented
                while i < len(lines) and lines[i].startswith("  ") and lines[i].strip() and not re.match(r"^\s*[-*]\s+", lines[i]):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            blocks.append(Block("list", items=items))
            continue

        # Numbered list
        if re.match(r"^\s*\d+\.\s+", ln):
            items = []
            while i < len(lines) and re.match(r"^\s*\d+\.\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+\.\s+", "", lines[i]))
                i += 1
                while i < len(lines) and lines[i].startswith("   ") and lines[i].strip() and not re.match(r"^\s*\d+\.\s+", lines[i]):
                    items[-1] += " " + lines[i].strip()
                    i += 1
            blocks.append(Block("olist", items=items))
            continue

        # Blockquote
        if stripped.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].lstrip())
                i += 1
            blocks.append(Block("blockquote", text="\n".join(buf)))
            continue

        # Paragraph — one or more non-empty lines
        buf = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not _is_block_start(lines[i]):
            buf.append(lines[i])
            i += 1
        blocks.append(Block("paragraph", text="\n".join(buf)))

    return title, metadata, blocks


def _split_table_row(ln: str) -> list[str]:
    s = ln.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    # naive split — pipes inside code spans are not common in our reports
    return s.split("|")


def _is_block_start(ln: str) -> bool:
    s = ln.strip()
    if not s:
        return True
    if s.startswith("#") or s.startswith("```") or s.startswith(">"):
        return True
    if re.match(r"^\s*[-*]\s+", ln) or re.match(r"^\s*\d+\.\s+", ln):
        return True
    if s in {"---", "***", "___"}:
        return True
    return False


# ─── Inline rendering ────────────────────────────────────────────────────────

CODE_SPAN_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*]+?)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
TAG_RE = re.compile(r"^\[([A-Z]+)\]\s*(.*)$")  # for drift section H3s


def render_inline(text: str) -> str:
    """Render inline markdown to HTML. Handles `code`, **bold**, *italic*, [text](url).
    Code spans are protected first so their content isn't further mangled."""
    placeholders: list[str] = []

    def stash_code(m: re.Match) -> str:
        placeholders.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00CODE{len(placeholders) - 1}\x00"

    out = CODE_SPAN_RE.sub(stash_code, text)
    out = html.escape(out)
    # Restore code (the placeholders contain unescaped <code>)
    for idx, code in enumerate(placeholders):
        out = out.replace(f"\x00CODE{idx}\x00", code)
    out = BOLD_RE.sub(r"<strong>\1</strong>", out)
    out = ITALIC_RE.sub(r"<em>\1</em>", out)
    out = LINK_RE.sub(lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{m.group(1)}</a>', out)
    return out


# ─── Per-kind interpretation ─────────────────────────────────────────────────

VERDICT_TONE = {"PASS": "success", "FAIL": "error", "PARTIAL": "warning", "BLOCKED": "warning"}
SEVERITY_TONE = {"none": "info", "minor": "warning", "major": "warning", "critical": "error"}
STATUS_CELL_TONE = {"PASS": "success", "FAIL": "error", "WARN": "warning", "WARNING": "warning",
                    "SKIP": "info", "N/A": "info"}
DRIFT_TAG_TONE = {"UPDATE": "interactive", "SMELL": "error", "PLANNED": "success", "INFO": "info"}


def interpret(report_path: Path, raw_text: str) -> Report:
    yaml, body = split_yaml_frontmatter(raw_text)
    kind = detect_kind(report_path, yaml.get("kind"))
    title, metadata, blocks = parse_markdown(body)

    # Merge YAML keys into metadata, YAML wins
    md_dict = {k.lower(): v for k, v in metadata}
    for k, v in yaml.items():
        if k.lower() == "kind":
            continue
        md_dict[k.lower()] = v
        # also update ordered list — replace if present, else append
        idx = next((i for i, (kk, _) in enumerate(metadata) if kk.lower() == k.lower()), None)
        if idx is None:
            metadata.append((k.title(), v))
        else:
            metadata[idx] = (metadata[idx][0], v)

    verdict = md_dict.get("verdict")
    severity = None
    status = md_dict.get("status")

    # Drift: pull severity from a "## Severity: **minor**" tail line, then drop that block
    if kind == KIND_DRIFT:
        for j, b in enumerate(blocks):
            if b.kind == "h2" and b.text.lower().startswith("severity"):
                # text might be 'Severity: **minor**' OR header 'Severity' followed by content
                tail = b.text.split(":", 1)[1].strip() if ":" in b.text else ""
                tail = tail.replace("*", "").strip().lower()
                if tail in SEVERITY_TONE:
                    severity = tail
                    blocks[j] = Block("__skip__")
                    # Also skip the next paragraph if it just restates the level
                    if j + 1 < len(blocks) and blocks[j + 1].kind == "paragraph":
                        if blocks[j + 1].text.strip().lower().replace("*", "") in SEVERITY_TONE:
                            blocks[j + 1] = Block("__skip__")
                break
        if severity is None:
            # Fallback: scan paragraphs for "Severity: minor"
            for b in blocks:
                if b.kind == "paragraph":
                    m = re.search(r"severity[:\s*]+(\*+)?(\w+)", b.text, re.IGNORECASE)
                    if m and m.group(2).lower() in SEVERITY_TONE:
                        severity = m.group(2).lower()
                        break
        blocks = [b for b in blocks if b.kind != "__skip__"]

    return Report(
        title=title,
        metadata=metadata,
        blocks=blocks,
        kind=kind,
        yaml=yaml,
        severity=severity,
        verdict=verdict,
        status=status,
    )


# ─── HTML rendering ──────────────────────────────────────────────────────────

CSS = r"""
:root {
  --nd-black: #000000;
  --nd-surface: #111111;
  --nd-surface-raised: #1a1a1a;
  --nd-border: #222222;
  --nd-border-visible: #333333;
  --nd-text-disabled: #666666;
  --nd-text-secondary: #999999;
  --nd-text-primary: #e8e8e8;
  --nd-text-display: #ffffff;

  --nd-accent: #d71921;
  --nd-accent-subtle: rgba(215, 25, 33, 0.15);
  --nd-success: #4a9e5c;
  --nd-warning: #d4a843;
  --nd-error: #d71921;
  --nd-info: #999999;
  --nd-interactive: #5b9bf6;

  --nd-font-display: 'Space Grotesk', 'DM Sans', system-ui, sans-serif;
  --nd-font-body: 'Space Grotesk', 'DM Sans', system-ui, sans-serif;
  --nd-font-mono: 'Fira Code', 'JetBrains Mono', ui-monospace, 'SF Mono', monospace;

  --nd-size-display-md: 36px;
  --nd-size-heading: 24px;
  --nd-size-subheading: 18px;
  --nd-size-body: 16px;
  --nd-size-body-sm: 14px;
  --nd-size-caption: 12px;
  --nd-size-label: 11px;

  --nd-lh-display: 1.05;
  --nd-lh-heading: 1.2;
  --nd-lh-body: 1.5;
  --nd-tracking-tight: -0.02em;
  --nd-tracking-label: 0.08em;

  --nd-weight-regular: 400;
  --nd-weight-medium: 500;
  --nd-weight-bold: 700;

  --nd-space-xs: 4px;
  --nd-space-sm: 8px;
  --nd-space-md: 16px;
  --nd-space-lg: 24px;
  --nd-space-xl: 32px;
  --nd-space-2xl: 48px;

  --nd-radius-sm: 4px;
  --nd-radius-md: 8px;
  --nd-radius-pill: 999px;

  --nd-ease: cubic-bezier(0.25, 0.1, 0.25, 1);
}

[data-theme="light"] {
  --nd-black: #f5f5f5;
  --nd-surface: #ffffff;
  --nd-surface-raised: #f0f0f0;
  --nd-border: #e8e8e8;
  --nd-border-visible: #cccccc;
  --nd-text-disabled: #999999;
  --nd-text-secondary: #666666;
  --nd-text-primary: #1a1a1a;
  --nd-text-display: #000000;
  --nd-interactive: #007aff;
}

*, *::before, *::after { box-sizing: border-box; }
* { margin: 0; padding: 0; }
html { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
body {
  font-family: var(--nd-font-body);
  font-size: var(--nd-size-body);
  line-height: var(--nd-lh-body);
  color: var(--nd-text-primary);
  background: var(--nd-black);
  min-height: 100vh;
  padding: var(--nd-space-2xl) var(--nd-space-lg);
}
a { color: var(--nd-interactive); text-decoration: none; }
a:hover { color: var(--nd-text-display); }

.report {
  max-width: 880px;
  margin: 0 auto;
}

.report__header {
  border-bottom: 1px solid var(--nd-border);
  padding-bottom: var(--nd-space-lg);
  margin-bottom: var(--nd-space-xl);
}
.report__eyebrow {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-secondary);
  margin-bottom: var(--nd-space-sm);
}
.report__title {
  font-family: var(--nd-font-display);
  font-size: var(--nd-size-display-md);
  font-weight: var(--nd-weight-medium);
  line-height: var(--nd-lh-display);
  letter-spacing: var(--nd-tracking-tight);
  color: var(--nd-text-display);
  margin-bottom: var(--nd-space-md);
}
.report__pills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--nd-space-sm);
  margin-bottom: var(--nd-space-md);
}
.report__meta {
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: var(--nd-space-xs) var(--nd-space-md);
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-caption);
  color: var(--nd-text-secondary);
}
.report__meta dt {
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
}
.report__meta dd { color: var(--nd-text-primary); word-break: break-word; }

/* Bracketed status pills */
.pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  font-weight: var(--nd-weight-medium);
}
.pill::before { content: "["; color: var(--nd-text-secondary); }
.pill::after  { content: "]"; color: var(--nd-text-secondary); }
.pill--success { color: var(--nd-success); }
.pill--warning { color: var(--nd-warning); }
.pill--error   { color: var(--nd-error); }
.pill--info    { color: var(--nd-info); }
.pill--interactive { color: var(--nd-interactive); }
.pill--accent { color: var(--nd-accent); }

/* Sections */
.report h2 {
  font-family: var(--nd-font-display);
  font-size: var(--nd-size-heading);
  font-weight: var(--nd-weight-medium);
  line-height: var(--nd-lh-heading);
  color: var(--nd-text-display);
  margin: var(--nd-space-2xl) 0 var(--nd-space-md);
  padding-top: var(--nd-space-lg);
  border-top: 1px solid var(--nd-border);
  letter-spacing: var(--nd-tracking-tight);
}
.report h2:first-of-type { border-top: 0; padding-top: 0; margin-top: var(--nd-space-md); }
.report h3 {
  font-family: var(--nd-font-display);
  font-size: var(--nd-size-subheading);
  font-weight: var(--nd-weight-medium);
  color: var(--nd-text-display);
  margin: var(--nd-space-xl) 0 var(--nd-space-sm);
  display: flex;
  align-items: center;
  gap: var(--nd-space-sm);
}
.report h4 {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-caption);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-secondary);
  margin: var(--nd-space-lg) 0 var(--nd-space-sm);
}

.report p { margin: var(--nd-space-sm) 0; color: var(--nd-text-primary); }
.report p code, .report li code, .report td code, .report dd code {
  font-family: var(--nd-font-mono);
  font-size: 0.92em;
  background: var(--nd-surface);
  border: 1px solid var(--nd-border);
  padding: 1px 6px;
  border-radius: var(--nd-radius-sm);
  color: var(--nd-text-primary);
}

.report ul, .report ol { padding-left: var(--nd-space-lg); margin: var(--nd-space-sm) 0; }
.report li { margin: var(--nd-space-xs) 0; }
.report li::marker { color: var(--nd-text-secondary); }

.report ul.accent--warning {
  border-left: 2px solid var(--nd-warning);
  padding-left: var(--nd-space-md);
  list-style: none;
  margin-left: 0;
}
.report ul.accent--info {
  border-left: 2px solid var(--nd-interactive);
  padding-left: var(--nd-space-md);
  list-style: none;
  margin-left: 0;
}
.report ul.accent--error {
  border-left: 2px solid var(--nd-error);
  padding-left: var(--nd-space-md);
  list-style: none;
  margin-left: 0;
}

.report blockquote {
  border-left: 2px solid var(--nd-border-visible);
  padding-left: var(--nd-space-md);
  color: var(--nd-text-secondary);
  margin: var(--nd-space-md) 0;
  font-style: normal;
}

/* Tables — flat surfaces, hover on raised */
.report table {
  width: 100%;
  border-collapse: collapse;
  margin: var(--nd-space-md) 0;
  font-size: var(--nd-size-body-sm);
}
.report thead th {
  text-align: left;
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-secondary);
  font-weight: var(--nd-weight-regular);
  padding: var(--nd-space-sm) var(--nd-space-md);
  border-bottom: 1px solid var(--nd-border-visible);
  background: transparent;
}
.report tbody td {
  padding: var(--nd-space-sm) var(--nd-space-md);
  border-bottom: 1px solid var(--nd-border);
  color: var(--nd-text-primary);
  vertical-align: top;
}
.report tbody tr:hover td { background: var(--nd-surface-raised); }
.report td.status-cell { font-family: var(--nd-font-mono); }
.report td.status-cell.success { color: var(--nd-success); }
.report td.status-cell.warning { color: var(--nd-warning); }
.report td.status-cell.error   { color: var(--nd-error); }
.report td.status-cell.info    { color: var(--nd-info); }

/* Code blocks */
.report pre {
  background: var(--nd-surface);
  border: 1px solid var(--nd-border);
  border-radius: var(--nd-radius-md);
  padding: var(--nd-space-md);
  overflow-x: auto;
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-body-sm);
  margin: var(--nd-space-md) 0;
  color: var(--nd-text-primary);
}
.report pre code { background: transparent; border: 0; padding: 0; }

/* Mermaid diagrams — rendered to SVG at build time and embedded as <img>. */
.report .mermaid-figure {
  background: var(--nd-surface);
  border: 1px solid var(--nd-border);
  border-radius: var(--nd-radius-md);
  padding: var(--nd-space-lg) var(--nd-space-md);
  margin: var(--nd-space-md) 0;
  overflow-x: auto;
  text-align: center;
}
.report .mermaid-figure img {
  max-width: 100%;
  height: auto;
  display: inline-block;
  vertical-align: middle;
}
.report .mermaid-figure--fallback {
  text-align: left;
}
.report .mermaid-fallback-note {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-secondary);
  margin-bottom: var(--nd-space-sm);
}
.report .mermaid-fallback-note::before { content: "[ "; color: var(--nd-text-secondary); }
.report .mermaid-fallback-note::after  { content: " ]"; color: var(--nd-text-secondary); }

/* Analysis reports often use bracketed conceptual nodes like &lt;ConceptName&gt;
   and ASCII box diagrams in the prose. Keep them legible. */
.report > article p code, .report > article li code {
  font-family: var(--nd-font-mono);
}

.empty-placeholder {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-disabled);
}
.empty-placeholder::before { content: "[ "; color: var(--nd-text-disabled); }
.empty-placeholder::after  { content: " ]"; color: var(--nd-text-disabled); }

/* Footer */
.report__footer {
  margin-top: var(--nd-space-2xl);
  padding-top: var(--nd-space-lg);
  border-top: 1px solid var(--nd-border);
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-disabled);
  display: flex;
  justify-content: space-between;
  gap: var(--nd-space-md);
}

/* Bundle layout */
.bundle {
  display: grid;
  grid-template-columns: 320px 1fr;
  min-height: 100vh;
  max-width: 1280px;
  margin: 0 auto;
  background: var(--nd-black);
}
.bundle__rail {
  border-right: 1px solid var(--nd-border);
  padding: var(--nd-space-lg) var(--nd-space-md);
  overflow-y: auto;
  max-height: 100vh;
  position: sticky;
  top: 0;
}
.bundle__brand {
  font-family: var(--nd-font-display);
  font-size: var(--nd-size-heading);
  font-weight: var(--nd-weight-medium);
  letter-spacing: var(--nd-tracking-tight);
  color: var(--nd-text-display);
  margin-bottom: var(--nd-space-xs);
}
.bundle__sub {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-secondary);
  margin-bottom: var(--nd-space-lg);
}
.bundle__group { margin-bottom: var(--nd-space-lg); }
.bundle__group-title {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-secondary);
  margin-bottom: var(--nd-space-sm);
}
.bundle__item {
  display: flex;
  flex-direction: column;
  padding: var(--nd-space-sm) var(--nd-space-md);
  border-left: 2px solid transparent;
  cursor: pointer;
  transition: background var(--nd-duration-fast, 150ms) var(--nd-ease),
              border-color var(--nd-duration-fast, 150ms) var(--nd-ease);
  gap: 4px;
}
.bundle__item:hover { background: var(--nd-surface-raised); }
.bundle__item.is-active {
  background: var(--nd-surface);
  border-left-color: var(--nd-accent);
}
.bundle__item-title {
  color: var(--nd-text-primary);
  font-size: var(--nd-size-body-sm);
}
.bundle__item-meta {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-secondary);
}
.bundle__main {
  padding: var(--nd-space-2xl) var(--nd-space-xl);
  overflow-y: auto;
  max-height: 100vh;
}
.bundle__empty {
  font-family: var(--nd-font-mono);
  font-size: var(--nd-size-label);
  letter-spacing: var(--nd-tracking-label);
  text-transform: uppercase;
  color: var(--nd-text-disabled);
  text-align: center;
  padding: var(--nd-space-2xl);
}
@media (max-width: 768px) {
  .bundle { grid-template-columns: 1fr; }
  .bundle__rail { position: static; max-height: none; border-right: 0; border-bottom: 1px solid var(--nd-border); }
  .bundle__main { padding: var(--nd-space-lg) var(--nd-space-md); }
}
"""


def render_block(block: Block, *, kind: str | None) -> str:
    """Render a block to HTML with per-kind treatments."""
    if block.kind == "h1":
        return f"<h2>{render_inline(block.text)}</h2>"  # demote stray H1s in body
    if block.kind == "h2":
        # Static-Checks section: if the table inside has "No findings", we'll handle in table
        return f"<h2>{render_inline(block.text)}</h2>"
    if block.kind == "h3":
        # Drift sub-sections often start with [TAG]
        m = TAG_RE.match(block.text)
        if kind == KIND_DRIFT and m:
            tag, rest = m.group(1), m.group(2)
            tone = DRIFT_TAG_TONE.get(tag, "info")
            return f'<h3><span class="pill pill--{tone}">{html.escape(tag)}</span>{render_inline(rest)}</h3>'
        return f"<h3>{render_inline(block.text)}</h3>"
    if block.kind == "h4":
        return f"<h4>{render_inline(block.text)}</h4>"
    if block.kind == "paragraph":
        # collapse newlines into spaces inside a paragraph
        text = " ".join(block.text.splitlines())
        return f"<p>{render_inline(text)}</p>"
    if block.kind == "blockquote":
        text = " ".join(block.text.splitlines())
        return f"<blockquote>{render_inline(text)}</blockquote>"
    if block.kind == "hr":
        return ""  # drop horizontal rules — section borders provide separation
    if block.kind == "code":
        body = html.escape(block.text)
        cls = f' class="lang-{html.escape(block.lang)}"' if block.lang else ""
        return f"<pre><code{cls}>{body}</code></pre>"
    if block.kind == "mermaid":
        # Reached only when render_block_with_extras was bypassed; treat as
        # source listing so we never silently drop content.
        body = html.escape(block.text)
        return f'<pre><code class="lang-mermaid">{body}</code></pre>'
    if block.kind == "list":
        accent = block.extras.get("accent")
        cls = f' class="accent--{accent}"' if accent else ""
        items = "".join(f"<li>{render_inline(it)}</li>" for it in block.items)
        return f"<ul{cls}>{items}</ul>"
    if block.kind == "olist":
        items = "".join(f"<li>{render_inline(it)}</li>" for it in block.items)
        return f"<ol>{items}</ol>"
    if block.kind == "table":
        return render_table(block)
    if block.kind == "metadata":
        return ""
    if block.kind == "empty":
        return '<p class="empty-placeholder">empty</p>'
    return ""


def render_table(block: Block) -> str:
    headers = block.headers
    rows = block.rows
    # Find a column literally named Status / status — its cells will be coloured
    status_col = next((i for i, h in enumerate(headers) if h.strip().lower() == "status"), None)

    head_html = "".join(f"<th>{render_inline(h)}</th>" for h in headers)
    body_html_parts: list[str] = []
    for r in rows:
        cells: list[str] = []
        for i, c in enumerate(r):
            content = render_inline(c)
            if i == status_col:
                tone = STATUS_CELL_TONE.get(c.strip().upper(), "info")
                cells.append(f'<td class="status-cell {tone}">{content}</td>')
            else:
                cells.append(f"<td>{content}</td>")
        body_html_parts.append(f"<tr>{''.join(cells)}</tr>")
    return (
        "<table>"
        f"<thead><tr>{head_html}</tr></thead>"
        f"<tbody>{''.join(body_html_parts)}</tbody>"
        "</table>"
    )


# Sections that get a coloured left-border accent on their list
KIND_SECTION_ACCENTS = {
    KIND_BAILIFF: {
        "warnings": "warning",
        "suggested fixes": "info",
    },
    KIND_BUILD: {
        "deviations from plan": "warning",
        "tradeoffs": "warning",
        "open items": "error",
    },
}

# Sections where a single-line "None." should render as a [ NONE ] pill
NONE_PILL_SECTIONS = {KIND_BUILD: {"deviations from plan", "open items"}}


def post_process(report: Report) -> list[Block]:
    """Apply per-kind treatments: list accents, [ CLEAN ] / [ NONE ] markers, empty placeholders."""
    blocks = report.blocks
    section_accents = KIND_SECTION_ACCENTS.get(report.kind or "", {})
    none_pill_sections = NONE_PILL_SECTIONS.get(report.kind or "", set())

    out: list[Block] = []
    current_h2 = ""
    for idx, b in enumerate(blocks):
        if b.kind == "h2":
            current_h2 = b.text.strip().lower()
            out.append(b)
            # Look ahead — if the H2 has no body before next H2/EOF, mark empty
            j = idx + 1
            while j < len(blocks) and blocks[j].kind in {"hr"}:
                j += 1
            if j >= len(blocks) or blocks[j].kind == "h2":
                out.append(Block("empty"))
            continue

        if b.kind == "list" and current_h2 in section_accents:
            b.extras["accent"] = section_accents[current_h2]

        if b.kind == "paragraph" and current_h2 in none_pill_sections:
            if b.text.strip().rstrip(".").strip().lower() == "none":
                # Replace with a [ NONE ] pill in a paragraph
                out.append(Block("paragraph", text='<span class="pill pill--success">NONE</span>',
                                 extras={"raw_html": True}))
                continue

        # Static Checks: detect "No findings" in a table → prepend [ CLEAN ]
        if (
            report.kind == KIND_BAILIFF
            and current_h2 == "static checks"
            and b.kind == "table"
        ):
            flat = " ".join(" ".join(r) for r in b.rows).lower()
            if "no findings" in flat:
                out.append(Block("paragraph", text='<span class="pill pill--success">CLEAN</span>',
                                 extras={"raw_html": True}))

        out.append(b)

    return out


def render_block_with_extras(block: Block, *, kind: str | None,
                             mermaid_resolutions: dict[int, "_MermaidResolution"] | None = None) -> str:
    if block.extras.get("raw_html"):
        return f"<p>{block.text}</p>"
    if block.kind == "mermaid":
        res = (mermaid_resolutions or {}).get(id(block))
        if res is not None and res.svg_filename is not None:
            # Pull the diagram caption from a leading comment (`%% caption: …`),
            # or fall back to a short sample of the source for the alt text.
            caption_match = re.match(r"\s*%%\s*(?:caption|title)\s*:\s*(.+)",
                                     block.text, re.IGNORECASE)
            if caption_match:
                alt = caption_match.group(1).strip()
            else:
                first = block.text.lstrip().splitlines()[0] if block.text.strip() else "diagram"
                alt = (f"mermaid diagram — {first}").strip()[:160]
            return (
                '<figure class="mermaid-figure">'
                f'<img src="{html.escape(res.svg_filename, quote=True)}" '
                f'alt="{html.escape(alt, quote=True)}" '
                'loading="lazy" decoding="async" />'
                '</figure>'
            )
        # Fallback: every renderer failed (or mode == none). Keep the source
        # visible so the reader at least sees what was meant to be there.
        body = html.escape(block.text)
        return (
            '<figure class="mermaid-figure mermaid-figure--fallback">'
            '<figcaption class="mermaid-fallback-note">'
            'diagram source — render unavailable'
            '</figcaption>'
            f'<pre><code class="lang-mermaid">{body}</code></pre>'
            '</figure>'
        )
    return render_block(block, kind=kind)


# ─── Page assembly ───────────────────────────────────────────────────────────

KIND_LABEL = {
    KIND_BAILIFF: "Bailiff Report",
    KIND_BUILD: "Build Report",
    KIND_DRIFT: "Drift Report",
    KIND_ANALYSIS: "Analysis Report",
}


def render_header_pills(report: Report) -> str:
    pills: list[str] = []
    if report.kind == KIND_BAILIFF and report.verdict:
        v = report.verdict.strip().upper()
        tone = VERDICT_TONE.get(v, "info")
        pills.append(f'<span class="pill pill--{tone}">{html.escape(v)}</span>')
    if report.kind == KIND_DRIFT:
        if report.severity:
            tone = SEVERITY_TONE.get(report.severity.lower(), "info")
            pills.append(f'<span class="pill pill--{tone}">{html.escape(report.severity.upper())}</span>')
        if report.status:
            pills.append(f'<span class="pill pill--info">{html.escape(report.status.upper())}</span>')
    return "".join(pills)


def render_metadata_dl(report: Report) -> str:
    if not report.metadata:
        return ""
    rows: list[str] = []
    for k, v in report.metadata:
        # Suppress fields already shown as pills
        if report.kind == KIND_BAILIFF and k.lower() == "verdict":
            continue
        if report.kind == KIND_DRIFT and k.lower() in {"severity", "status"}:
            # status sometimes shows in metadata too — keep it visible there for completeness
            if k.lower() == "severity":
                continue
        rows.append(f"<dt>{html.escape(k)}</dt><dd>{render_inline(v)}</dd>")
    return f'<dl class="report__meta">{"".join(rows)}</dl>'


def render_report_inner(report: Report,
                        mermaid_resolutions: dict[int, "_MermaidResolution"] | None = None) -> str:
    blocks = post_process(report)
    body = "\n".join(
        render_block_with_extras(b, kind=report.kind, mermaid_resolutions=mermaid_resolutions)
        for b in blocks
    )
    eyebrow = KIND_LABEL.get(report.kind or "", "Report")
    pills = render_header_pills(report)
    meta = render_metadata_dl(report)
    title = render_inline(report.title) if report.title else "Untitled"
    pills_html = f'<div class="report__pills">{pills}</div>' if pills else ""
    meta_html = meta or ""
    return (
        '<article class="report">'
        '<header class="report__header">'
        f'<div class="report__eyebrow">{html.escape(eyebrow)}</div>'
        f'<h1 class="report__title">{title}</h1>'
        f'{pills_html}'
        f'{meta_html}'
        "</header>"
        f"{body}"
        "</article>"
    )


# ─── Mermaid → SVG pipeline ──────────────────────────────────────────────────
#
# We render diagrams to SVG at build time and embed them as sibling files via
# `<img src="diagram-<hash>.svg">`. This is more reliable than a JS runtime —
# diagrams that fail to render fail HERE, with a stderr message and the source
# preserved as a `<pre>` fallback, rather than silently breaking in the
# reader's browser.
#
# Three render paths, tried in order when mode == "auto":
#
#   1. mmdc — local @mermaid-js/mermaid-cli via `npx`. Fully offline, themable
#      via a JSON config we ship next to the diagram. Requires Node + Chromium
#      shared libs on the host (see SKILL.md "mmdc setup" section).
#   2. kroki — POST to https://kroki.io/mermaid/svg. Needs internet but no
#      local toolchain, and gracefully handles every mermaid feature.
#   3. fallback — leave the source in a `<pre>` block so the reader can at
#      least see what was meant to be there.
#
# Rendered SVGs are cached under <output_dir>/.mermaid-cache/<hash>.svg —
# content-addressed so identical diagrams reuse the same render across reports
# and rebuilds.

MERMAID_CACHE_DIRNAME = ".mermaid-cache"
MMDC_PROBE_TIMEOUT = 10  # seconds — kept short so `auto` doesn't stall a build
MMDC_RENDER_TIMEOUT = 60
KROKI_TIMEOUT = 30
# Use the JSON endpoint so we can request a dark theme — the bare /mermaid/svg
# POST endpoint always uses the default light theme.
KROKI_URL_JSON = "https://kroki.io/"


def _mermaid_hash(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()[:12]


# Cache mmdc availability between calls within a single run.
_MMDC_AVAILABLE: bool | None = None


def _mmdc_available() -> bool:
    """Probe whether mmdc can actually render. Result is cached for this run."""
    global _MMDC_AVAILABLE
    if _MMDC_AVAILABLE is not None:
        return _MMDC_AVAILABLE
    try:
        # Probe with `--version` rather than rendering — fast, no Chromium spawn
        # required for the CLI itself to print the version. (The actual render
        # call is what may fail with libatk-bridge, captured at render time.)
        r = subprocess.run(
            ["npx", "--yes", "-p", "@mermaid-js/mermaid-cli", "mmdc", "--version"],
            capture_output=True, text=True, timeout=MMDC_PROBE_TIMEOUT,
        )
        _MMDC_AVAILABLE = (r.returncode == 0)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        _MMDC_AVAILABLE = False
    return _MMDC_AVAILABLE


# Theme config passed to mmdc. Mirrors the nothing-design tokens — the CSS in
# the rendered SVG inherits these values so the diagram blends with the page.
_MMDC_THEME_VARS = {
    "darkMode": True,
    "background": "#111111",
    "primaryColor": "#1a1a1a",
    "primaryTextColor": "#e8e8e8",
    "primaryBorderColor": "#333333",
    "lineColor": "#999999",
    "secondaryColor": "#1a1a1a",
    "tertiaryColor": "#111111",
    "noteBkgColor": "#1a1a1a",
    "noteTextColor": "#e8e8e8",
    "noteBorderColor": "#333333",
    "actorBkg": "#1a1a1a",
    "actorBorder": "#333333",
    "actorTextColor": "#e8e8e8",
    "signalColor": "#999999",
    "signalTextColor": "#e8e8e8",
    "labelBoxBkgColor": "#1a1a1a",
    "labelBoxBorderColor": "#333333",
    "labelTextColor": "#e8e8e8",
    "altBackground": "#0a0a0a",
}


def _render_mmdc(source: str) -> str | None:
    """Render with local mmdc. Returns SVG text or None on failure."""
    if not _mmdc_available():
        return None
    with tempfile.TemporaryDirectory(prefix="herald-mmdc-") as tmp:
        tmp_path = Path(tmp)
        in_path = tmp_path / "diagram.mmd"
        out_path = tmp_path / "diagram.svg"
        cfg_path = tmp_path / "config.json"
        in_path.write_text(source, encoding="utf-8")
        cfg_path.write_text(json.dumps({
            "theme": "dark",
            "themeVariables": _MMDC_THEME_VARS,
            "fontFamily": "'Fira Code', 'JetBrains Mono', ui-monospace, monospace",
        }), encoding="utf-8")
        try:
            r = subprocess.run(
                [
                    "npx", "--yes", "-p", "@mermaid-js/mermaid-cli", "mmdc",
                    "-i", str(in_path),
                    "-o", str(out_path),
                    "-c", str(cfg_path),
                    "-b", "transparent",
                ],
                capture_output=True, text=True, timeout=MMDC_RENDER_TIMEOUT,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError) as e:
            print(f"herald: mmdc render failed: {e}", file=sys.stderr)
            return None
        if r.returncode != 0 or not out_path.is_file():
            # First failure is enough to disable mmdc for the rest of the run.
            global _MMDC_AVAILABLE
            _MMDC_AVAILABLE = False
            err_tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
            print("herald: mmdc render failed (disabling mmdc for this run): "
                  + " | ".join(err_tail), file=sys.stderr)
            return None
        return out_path.read_text(encoding="utf-8")


def _render_kroki(source: str) -> str | None:
    """Render with kroki.io. Returns SVG text or None on failure.

    We use the JSON endpoint so we can pass `diagram_options.theme: dark` —
    the bare /mermaid/svg endpoint always renders the default light theme.
    """
    try:
        import urllib.request
        import urllib.error
        payload = json.dumps({
            "diagram_source": source,
            "diagram_type": "mermaid",
            "output_format": "svg",
            "diagram_options": {"theme": "dark"},
        }).encode("utf-8")
        # Kroki rejects the default Python-urllib UA with 403, so set a UA
        # that looks like a normal client. The header value is cosmetic.
        req = urllib.request.Request(
            KROKI_URL_JSON,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "image/svg+xml",
                "User-Agent": "herald/1.0 (+https://github.com/tacit-skills/herald)",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=KROKI_TIMEOUT) as resp:
            body = resp.read().decode("utf-8")
            if not body.lstrip().startswith("<"):
                return None
            return body
    except (urllib.error.URLError, OSError, TimeoutError, ValueError) as e:
        print(f"herald: kroki render failed: {e}", file=sys.stderr)
        return None


def _render_mermaid_svg(source: str, mode: str) -> tuple[str | None, str]:
    """Resolve mode → SVG. Returns (svg_text_or_None, path_used).

    `path_used` is one of: "mmdc", "kroki", "none" (mode says off), or
    "fallback" (every renderer failed and the source survives as a <pre>).
    """
    if mode == "none":
        return None, "none"
    order: list[str]
    if mode == "mmdc":
        order = ["mmdc"]
    elif mode == "kroki":
        order = ["kroki"]
    else:  # auto
        order = ["mmdc", "kroki"]
    for path in order:
        svg = _render_mmdc(source) if path == "mmdc" else _render_kroki(source)
        if svg:
            return svg, path
    return None, "fallback"


def _slim_svg(svg: str) -> str:
    """Strip the XML prolog and DOCTYPE so the SVG can be referenced via `<img>`
    or saved standalone without warnings. Keep the root <svg> attributes intact.
    """
    out = svg
    # Strip leading XML prolog and DOCTYPE — `<img>` doesn't need them.
    out = re.sub(r"^\s*<\?xml[^?]*\?>\s*", "", out, count=1)
    out = re.sub(r"^\s*<!DOCTYPE[^>]*>\s*", "", out, count=1)
    return out.strip()


@dataclass
class _MermaidResolution:
    """The result of trying to render one mermaid block."""
    block: Block
    svg_filename: str | None  # e.g. "diagram-3f0a1e2c1234.svg"
    svg_path: Path | None     # absolute, where the SVG was written
    used: str                 # "mmdc" | "kroki" | "none" | "fallback" | "cache"


def materialize_mermaid(report: Report, target_dir: Path, mode: str) -> list[_MermaidResolution]:
    """For each `mermaid` block in `report`, ensure an SVG sibling exists
    in `target_dir` and return what was done. Idempotent / cache-aware.
    """
    if not report.uses_mermaid:
        return []
    cache_dir = target_dir / MERMAID_CACHE_DIRNAME
    target_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: list[_MermaidResolution] = []
    for b in report.blocks:
        if b.kind != "mermaid":
            continue
        source = b.text
        h = _mermaid_hash(source)
        svg_filename = f"diagram-{h}.svg"
        cache_svg = cache_dir / svg_filename
        sibling_svg = target_dir / svg_filename

        used = "cache"
        if not cache_svg.is_file():
            svg, used = _render_mermaid_svg(source, mode)
            if svg is None:
                # No SVG produced — let the renderer fall back to <pre>.
                out.append(_MermaidResolution(b, None, None, used))
                continue
            cache_svg.write_text(_slim_svg(svg), encoding="utf-8")

        # Mirror the cached SVG into the workspace folder so `<img>` resolves
        # without serving a hidden directory. Same content, separate filename.
        if not sibling_svg.is_file() or sibling_svg.stat().st_size != cache_svg.stat().st_size:
            sibling_svg.write_bytes(cache_svg.read_bytes())
        out.append(_MermaidResolution(b, svg_filename, sibling_svg, used))
    return out


def render_single_html(report: Report, source: Path, *, target_dir: Path | None = None,
                       mermaid_mode: str | None = None) -> str:
    title = report.title or source.stem
    mode = mermaid_mode or config_mermaid_mode()
    # Resolve mermaid first so `render_report_inner` can use the resolutions
    # via a per-render lookup keyed by block identity.
    resolutions: dict[int, _MermaidResolution] = {}
    if report.uses_mermaid and target_dir is not None and mode != "none":
        for r in materialize_mermaid(report, target_dir, mode):
            resolutions[id(r.block)] = r
    inner = render_report_inner(report, mermaid_resolutions=resolutions)
    footer = (
        f'<footer class="report__footer">'
        f'<span>{html.escape(KIND_LABEL.get(report.kind or "", "report"))}</span>'
        f'<span>{html.escape(source.name)}</span>'
        f'</footer>'
    )
    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        f"<style>{CSS}</style>"
        "</head>"
        "<body>"
        f'<div class="report-wrap">{inner}{footer}</div>'
        "</body>"
        "</html>"
    )


# ─── Bundle mode ─────────────────────────────────────────────────────────────

BUNDLE_JS = r"""
(function () {
  var items = document.querySelectorAll('[data-report-id]');
  var main = document.getElementById('bundle-main');
  function activate(id) {
    items.forEach(function (el) {
      el.classList.toggle('is-active', el.getAttribute('data-report-id') === id);
    });
    var tpl = document.getElementById('payload-' + id);
    if (tpl) {
      main.innerHTML = tpl.innerHTML;
      window.scrollTo(0, 0);
      main.scrollTop = 0;
    }
  }
  items.forEach(function (el) {
    el.addEventListener('click', function () {
      activate(el.getAttribute('data-report-id'));
      history.replaceState(null, '', '#' + el.getAttribute('data-report-id'));
    });
  });
  var initial = (window.location.hash || '').replace('#', '') || (items[0] && items[0].getAttribute('data-report-id'));
  if (initial) activate(initial);
})();
"""


@dataclass
class BundleEntry:
    id: str
    source: Path
    report: Report
    inner_html: str


def find_reports(root: Path) -> list[Path]:
    """Recursively find files whose name matches a known kind, but skip the html/ output dir."""
    found: list[Path] = []
    for p in root.rglob("*.md"):
        # Skip if any segment is named "html"
        if any(seg == "html" for seg in p.parts):
            continue
        parts_norm = "/" + "/".join(p.parts)
        if (
            p.name.endswith("-bailiff.md")
            or p.name.endswith("-build.md")
            or DRIFT_FILENAME_RE.match(p.name)
            or ANALYSIS_FILENAME_RE.match(p.name)
            or "/.claude/analyses/" in parts_norm
        ):
            found.append(p)
    return found


def safe_id(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "-", s).strip("-").lower() or "report"


def render_bundle_html(entries: list[BundleEntry], root: Path,
                       *, target_dir: Path | None = None,
                       mermaid_mode: str | None = None) -> str:
    # Group by kind, order each group by mtime desc
    groups: dict[str, list[BundleEntry]] = {
        KIND_BAILIFF: [], KIND_BUILD: [], KIND_DRIFT: [], KIND_ANALYSIS: []
    }
    for e in entries:
        if e.report.kind in groups:
            groups[e.report.kind].append(e)
    for k in groups:
        groups[k].sort(key=lambda e: e.source.stat().st_mtime, reverse=True)

    rail_groups_html: list[str] = []
    for kind, label in (
        (KIND_BAILIFF, "Bailiff"),
        (KIND_BUILD, "Build"),
        (KIND_DRIFT, "Drift"),
        (KIND_ANALYSIS, "Analysis"),
    ):
        items = groups[kind]
        if not items:
            continue
        rows: list[str] = []
        for e in items:
            sub = e.report.title or e.source.stem
            meta_bits: list[str] = []
            if e.report.kind == KIND_BAILIFF and e.report.verdict:
                meta_bits.append(e.report.verdict.upper())
            if e.report.kind == KIND_DRIFT and e.report.severity:
                meta_bits.append(e.report.severity.upper())
            if e.report.kind == KIND_ANALYSIS:
                # Surface "Level: module / Depth: deep" if present in metadata
                md = {k.lower(): v for k, v in e.report.metadata}
                level = md.get("level") or md.get("scope")
                if level:
                    meta_bits.append(level.upper())
            meta_bits.append(e.source.name)
            rows.append(
                f'<div class="bundle__item" data-report-id="{html.escape(e.id, quote=True)}">'
                f'<div class="bundle__item-title">{render_inline(sub)}</div>'
                f'<div class="bundle__item-meta">{html.escape(" · ".join(meta_bits))}</div>'
                "</div>"
            )
        rail_groups_html.append(
            f'<div class="bundle__group">'
            f'<div class="bundle__group-title">{label} · {len(items)}</div>'
            f'{"".join(rows)}'
            "</div>"
        )

    payload_templates = "".join(
        f'<template id="payload-{html.escape(e.id, quote=True)}">{e.inner_html}</template>'
        for e in entries
    )

    rail_html = "".join(rail_groups_html) or '<div class="bundle__empty">No reports found</div>'

    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Reports — {html.escape(root.name)}</title>"
        f"<style>{CSS}</style>"
        "</head>"
        "<body>"
        '<div class="bundle">'
        '<aside class="bundle__rail">'
        '<div class="bundle__brand">Reports</div>'
        f'<div class="bundle__sub">{html.escape(str(root))}</div>'
        f"{rail_html}"
        "</aside>"
        '<main class="bundle__main" id="bundle-main"></main>'
        "</div>"
        f"{payload_templates}"
        f"<script>{BUNDLE_JS}</script>"
        "</body>"
        "</html>"
    )


# ─── Config & output path resolution ─────────────────────────────────────────

CONFIG_PATH = Path(os.path.expanduser("~/.config/tacit-skills/herald.yaml"))
LEGACY_CONFIG_PATH = Path(os.path.expanduser("~/.config/.herald.yaml"))
DEFAULT_OUTPUT_DIR = "~/www/html"
DEFAULT_EMIT_INDEX = False  # in bundle mode, skip the all-in-one index.html unless asked
DEFAULT_MERMAID = "auto"  # "auto" | "mmdc" | "kroki" | "none"
HERALD_ROOT = Path(__file__).resolve().parent.parent

# Docker-style readable container names: same word lists Docker uses for
# anonymous containers. Picking from these by hashing the workspace path makes
# non-VCS workspaces deterministic without needing to write any state.
_DOCKER_LEFT = (
    "amazing", "blissful", "bold", "boring", "clever", "compassionate",
    "competent", "condescending", "cool", "dazzling", "determined", "eager",
    "ecstatic", "elastic", "elated", "elegant", "eloquent", "epic", "fervent",
    "festive", "flamboyant", "focused", "friendly", "frosty", "gallant", "gifted",
    "goofy", "gracious", "happy", "hardcore", "heuristic", "hopeful", "hungry",
    "inspiring", "jolly", "jovial", "keen", "kind", "laughing", "loving",
    "lucid", "magical", "modest", "musing", "mystifying", "naughty", "nervous",
    "nifty", "nostalgic", "objective", "optimistic", "peaceful", "pedantic",
    "pensive", "practical", "priceless", "quirky", "quizzical", "recursing",
    "relaxed", "reverent", "romantic", "sad", "serene", "sharp", "silly",
    "sleepy", "stoic", "strange", "stupefied", "suspicious", "tender",
    "thirsty", "trusting", "unruffled", "upbeat", "vibrant", "vigilant",
    "vigorous", "wizardly", "wonderful", "xenodochial", "youthful", "zealous",
    "zen",
)

_DOCKER_RIGHT = (
    "agnesi", "albattani", "allen", "almeida", "antonelli", "archimedes",
    "ardinghelli", "aryabhata", "austin", "babbage", "banach", "banzai",
    "bardeen", "bartik", "bassi", "beaver", "bell", "benz", "bhabha",
    "bhaskara", "black", "blackburn", "blackwell", "bohr", "booth", "borg",
    "bose", "bouman", "boyd", "brahmagupta", "brattain", "brown", "buck",
    "burnell", "cannon", "carson", "cartwright", "carver", "cerf", "chandrasekhar",
    "chaplygin", "chatelet", "chatterjee", "chebyshev", "cohen", "chaum",
    "clarke", "colden", "cori", "cray", "curie", "darwin", "davinci", "dewdney",
    "dhawan", "diffie", "dijkstra", "dirac", "driscoll", "dubinsky", "easley",
    "edison", "einstein", "elbakyan", "elgamal", "elion", "ellis", "engelbart",
    "euclid", "euler", "faraday", "feistel", "fermat", "fermi", "feynman",
    "franklin", "gagarin", "galileo", "galois", "ganguly", "gates", "gauss",
    "germain", "goldberg", "goldstine", "goldwasser", "golick", "goodall",
    "gould", "greider", "grothendieck", "haibt", "hamilton", "haslett",
    "hawking", "hellman", "heisenberg", "hermann", "herschel", "hertz",
    "heyrovsky", "hodgkin", "hofstadter", "hoover", "hopper", "hugle",
    "hypatia", "ishizaka", "jackson", "jang", "jemison", "jennings", "jepsen",
    "johnson", "joliot", "jones", "kalam", "kapitsa", "kare", "keldysh",
    "keller", "kepler", "khayyam", "khorana", "kilby", "kirch", "knuth",
    "kowalevski", "lalande", "lamarr", "lamport", "leakey", "leavitt", "lederberg",
    "lehmann", "lewin", "lichterman", "liskov", "lovelace", "lumiere", "mahavira",
    "margulis", "matsumoto", "maxwell", "mayer", "mccarthy", "mcclintock",
    "mclaren", "mclean", "mcnulty", "mendel", "mendeleev", "meitner", "meninsky",
    "merkle", "mestorf", "mirzakhani", "moore", "morse", "moser", "murdock",
    "napier", "nash", "neumann", "newton", "nightingale", "nobel", "noether",
    "northcutt", "noyce", "panini", "pare", "pascal", "pasteur", "payne",
    "perlman", "pike", "poincare", "poitras", "ptolemy", "raman", "ramanujan",
    "ride", "ritchie", "robinson", "roentgen", "rosalind", "rubin", "saha",
    "sammet", "sanderson", "satoshi", "shamir", "shannon", "shaw", "shirley",
    "shockley", "shtern", "sinoussi", "snyder", "solomon", "spence", "stonebraker",
    "sutherland", "swanson", "swartz", "swirles", "taussig", "tereshkova", "tesla",
    "tharp", "thompson", "torvalds", "tu", "turing", "varahamihira", "vaughan",
    "villani", "visvesvaraya", "volhard", "wescoff", "wilbur", "wiles", "williams",
    "williamson", "wing", "wozniak", "wright", "wu", "yalow", "yonath", "zhukovsky",
)


def load_config() -> dict[str, str]:
    """Parse ~/.config/tacit-skills/herald.yaml. Tiny `key: value` subset, no PyYAML dep.

    If the new path is empty but a legacy `~/.config/.herald.yaml` exists, read
    that instead (one-time read so the migration in ensure_config_with_defaults
    can rewrite it on next setup).
    """
    path = CONFIG_PATH if CONFIG_PATH.is_file() else (LEGACY_CONFIG_PATH if LEGACY_CONFIG_PATH.is_file() else None)
    if path is None:
        return {}
    cfg: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        ln = raw.split("#", 1)[0].strip()
        if not ln or ":" not in ln:
            continue
        k, v = ln.split(":", 1)
        cfg[k.strip()] = v.strip().strip("\"'")
    return cfg


def _truthy(v: str | None, default: bool = False) -> bool:
    if v is None:
        return default
    return v.strip().lower() in {"true", "yes", "on", "1"}


def config_emit_index() -> bool:
    """Should bundle mode emit the all-in-one index.html by default?"""
    return _truthy(load_config().get("emit_index"), default=DEFAULT_EMIT_INDEX)


def config_mermaid_mode() -> str:
    """How to render mermaid diagrams to SVG.

    Values:
      auto  — try mmdc first (offline, best fidelity), fall back to kroki.io,
              fall back to embedding the source as <pre>. Default.
      mmdc  — local mermaid-cli only. Fail loudly if mmdc isn't usable.
      kroki — POST to https://kroki.io/mermaid/svg. Needs internet.
      none  — render mermaid blocks as plain code listings, no SVG.
    """
    raw = (load_config().get("mermaid") or DEFAULT_MERMAID).strip().lower()
    if raw not in {"auto", "mmdc", "kroki", "none"}:
        return DEFAULT_MERMAID
    return raw


def resolve_output_root() -> Path:
    """Resolve the configured output_dir, falling back to the default."""
    cfg = load_config()
    raw = cfg.get("output_dir", DEFAULT_OUTPUT_DIR)
    return Path(os.path.expanduser(os.path.expandvars(raw))).resolve()


def find_workspace_root(p: Path) -> Path:
    """Return the workspace root for a path. Heuristic, in order:

    1. Nearest ancestor with a `.git` directory or file (worktree)
    2. Nearest ancestor with `.claude/`, `package.json`, `go.mod`, `pnpm-workspace.yaml`,
       `pyproject.toml`, or `Cargo.toml`
    3. Otherwise fall back to the input's parent directory.
    """
    markers_strong = (".git",)
    markers_soft = (".claude", "go.mod", "pnpm-workspace.yaml", "package.json",
                    "pyproject.toml", "Cargo.toml")
    candidates = [p, *p.parents]
    for parent in candidates:
        if any((parent / m).exists() for m in markers_strong):
            return parent
    for parent in candidates:
        if any((parent / m).exists() for m in markers_soft):
            return parent
    return p.parent


def git_info(workspace: Path) -> tuple[str, str] | None:
    """Return (branch, hash7) if `workspace` is inside a git repo, else None."""
    try:
        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=workspace, capture_output=True, text=True, timeout=5,
        )
        if branch.returncode != 0:
            return None
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=workspace, capture_output=True, text=True, timeout=5,
        )
        if sha.returncode != 0:
            return None
        b = branch.stdout.strip()
        h = sha.stdout.strip()
        if not b or not h:
            return None
        return b, h[:4]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


_SLUG_RE = re.compile(r"[^a-zA-Z0-9._-]+")


def slugify(s: str, *, fallback: str = "report") -> str:
    """Filesystem-safe slug. Slashes (e.g. `feature/foo` branches) become dashes."""
    out = _SLUG_RE.sub("-", s).strip("-.")
    return out or fallback


def docker_style_name(workspace: Path) -> str:
    """Stable, readable name for non-VCS workspaces. Same workspace path → same name."""
    digest = hashlib.sha256(str(workspace).encode("utf-8")).digest()
    left = _DOCKER_LEFT[digest[0] % len(_DOCKER_LEFT)]
    right = _DOCKER_RIGHT[digest[1] % len(_DOCKER_RIGHT)]
    return f"{left}-{right}"


def workspace_subdir(workspace: Path) -> str:
    """Compose `<workspace_basename>-<branch>-<hash4>` or `<workspace_basename>-<dockername>`."""
    base = slugify(workspace.name or "workspace")
    info = git_info(workspace)
    if info is not None:
        branch, hash4 = info
        return f"{base}-{slugify(branch)}-{hash4}"
    return f"{base}-{docker_style_name(workspace)}"


def output_dir_for(input_path: Path) -> Path:
    """The directory rendered HTML should land in for `input_path`."""
    workspace = find_workspace_root(input_path)
    return resolve_output_root() / workspace_subdir(workspace)


def default_output_path(input_path: Path) -> Path:
    """Where a single rendered report goes by default. See SKILL.md for the scheme."""
    return output_dir_for(input_path) / f"{input_path.stem}.html"


# ─── Top-level commands ──────────────────────────────────────────────────────

def render_one(input_path: Path, out_path: Path | None,
               *, mermaid_mode: str | None = None) -> Path:
    text = input_path.read_text(encoding="utf-8")
    report = interpret(input_path, text)
    if report.kind is None:
        raise SystemExit(
            f"herald: '{input_path}' doesn't match a known kind "
            "(*-bailiff.md, *-build.md, scout drift filename, or analysis filename "
            "YYYYMMDD_<level>_<target>.md). "
            "If this is a known kind, rename it or add YAML frontmatter "
            "with `kind: bailiff|build|drift|analysis`; otherwise herald isn't the right tool."
        )
    if report.kind == KIND_ANALYSIS and not report.title:
        # Analysis filenames carry signal (`20260514_module_foo.md`); fall back
        # to the basename if the markdown forgot the H1.
        report.title = input_path.stem
    if report.kind in {KIND_BAILIFF} and not report.verdict:
        print(f"herald: warning — {input_path.name} has no Verdict field; rendering without verdict pill.",
              file=sys.stderr)
    target = out_path or default_output_path(input_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    html_doc = render_single_html(report, input_path, target_dir=target.parent,
                                   mermaid_mode=mermaid_mode)
    target.write_text(html_doc, encoding="utf-8")
    return target


def render_bundle(
    root: Path,
    out_dir: Path | None,
    *,
    emit_index: bool = False,
    mermaid_mode: str | None = None,
) -> tuple[Path, list[Path]]:
    """Render every recognised report under `root`.

    Always writes per-report HTMLs into the workspace's output folder. Writes the
    all-in-one `index.html` switcher only when `emit_index` is true — most users
    serve the folder via a static webserver (or a self-hosted dashboard) and
    don't want a separate single-file aggregator. Returns the target dir and
    the list of files written, with `index.html` (if any) last.
    """
    sources = find_reports(root)
    if not sources:
        raise SystemExit(f"herald: no recognised reports found under {root}")

    # Pick a workspace anchor for the bundle. The bundle is one folder per
    # workspace, so the workspace is computed from `root` itself, not per-source.
    target_dir = out_dir or output_dir_for(root)
    target_dir.mkdir(parents=True, exist_ok=True)
    mode = mermaid_mode or config_mermaid_mode()

    entries: list[BundleEntry] = []
    seen_ids: set[str] = set()
    for src in sources:
        text = src.read_text(encoding="utf-8")
        report = interpret(src, text)
        if report.kind is None:
            continue
        rid_base = safe_id(src.stem)
        rid = rid_base
        n = 2
        while rid in seen_ids:
            rid = f"{rid_base}-{n}"
            n += 1
        seen_ids.add(rid)
        # Materialize SVGs into the workspace folder up front so both the
        # standalone HTML and the bundle index reference the same files.
        resolutions: dict[int, _MermaidResolution] = {}
        if report.uses_mermaid and mode != "none":
            for r in materialize_mermaid(report, target_dir, mode):
                resolutions[id(r.block)] = r
        inner = render_report_inner(report, mermaid_resolutions=resolutions)
        entries.append(BundleEntry(id=rid, source=src, report=report, inner_html=inner))

    written: list[Path] = []
    for e in entries:
        # render_single_html will repeat the materialize call, but the cache
        # makes it a free no-op. Pass mode through so warnings stay consistent.
        single_html = render_single_html(e.report, e.source, target_dir=target_dir,
                                          mermaid_mode=mode)
        path = target_dir / f"{e.source.stem}.html"
        path.write_text(single_html, encoding="utf-8")
        written.append(path)

    if emit_index:
        bundle_html = render_bundle_html(entries, root, target_dir=target_dir,
                                          mermaid_mode=mode)
        bundle_path = target_dir / "index.html"
        bundle_path.write_text(bundle_html, encoding="utf-8")
        written.append(bundle_path)

    return target_dir, written


def ensure_config() -> tuple[Path, bool]:
    """Create ~/.config/tacit-skills/herald.yaml with defaults if missing.

    Returns (path, created). One-time migration: if the legacy
    ~/.config/.herald.yaml exists and the new path is empty, move the contents
    over (and remove the old file) instead of writing fresh defaults.
    """
    if CONFIG_PATH.is_file():
        return CONFIG_PATH, False
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LEGACY_CONFIG_PATH.is_file():
        CONFIG_PATH.write_text(LEGACY_CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            LEGACY_CONFIG_PATH.unlink()
        except OSError:
            pass
        sys.stderr.write(f"herald: migrated legacy config {LEGACY_CONFIG_PATH} → {CONFIG_PATH}\n")
        return CONFIG_PATH, True
    CONFIG_PATH.write_text(
        "# herald — output configuration\n"
        "#\n"
        "# output_dir: where rendered HTML lives. Each workspace gets its own subfolder:\n"
        "#   <output_dir>/<workspace>-<branch>-<hash4>/     (input is in a git repo)\n"
        "#   <output_dir>/<workspace>-<docker-name>/        (no VCS info available)\n"
        "#\n"
        "# Tilde and $HOME are expanded. Defaults to ~/www/html so a local\n"
        "# `python -m http.server` from that dir serves every report.\n"
        f"output_dir: {DEFAULT_OUTPUT_DIR}\n"
        "\n"
        "# emit_index: in --bundle mode, also write an all-in-one index.html that\n"
        "# embeds every report and lets you click between them. Off by default —\n"
        "# most setups serve the folder via a self-hosted dashboard / static\n"
        "# webserver and don't need a second aggregator. CLI flags --index /\n"
        "# --no-index override this. Accepts: true / false / yes / no / on / off.\n"
        f"emit_index: {'true' if DEFAULT_EMIT_INDEX else 'false'}\n"
        "\n"
        "# mermaid: how analysis-report diagrams are rendered to SVG.\n"
        "#   auto  — try local mmdc first, then kroki.io, then leave the source\n"
        "#           as a code block. Default. Each render prints which path\n"
        "#           it took on stderr.\n"
        "#   mmdc  — local @mermaid-js/mermaid-cli only. Best fidelity, fully\n"
        "#           offline. Requires Node + Chromium shared libs (see SKILL.md).\n"
        "#   kroki — POST diagrams to https://kroki.io/mermaid/svg. Needs internet,\n"
        "#           no local toolchain.\n"
        "#   none  — render mermaid blocks as code listings, no diagram.\n"
        "#\n"
        "# Diagrams are rendered once per content hash and cached under\n"
        "# <output_dir>/<workspace>/.mermaid-cache/, then mirrored as siblings\n"
        "# of each report HTML for `<img>` resolution.\n"
        f"mermaid: {DEFAULT_MERMAID}\n",
        encoding="utf-8",
    )
    return CONFIG_PATH, True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="herald", description=__doc__)
    p.add_argument("input", nargs="?", help="Path to a markdown report (single mode).")
    p.add_argument("--bundle", metavar="DIR",
                   help="Render every recognised report under DIR. Per-report HTMLs always; index.html only if --index or emit_index: true in config.")
    p.add_argument("--out", metavar="PATH",
                   help="Override output path (single: file path; bundle: directory).")
    p.add_argument("--setup", action="store_true",
                   help="Create or check ~/.config/tacit-skills/herald.yaml and print the active output_dir.")
    idx = p.add_mutually_exclusive_group()
    idx.add_argument("--index", dest="emit_index", action="store_true", default=None,
                     help="In --bundle mode, also write index.html (overrides config).")
    idx.add_argument("--no-index", dest="emit_index", action="store_false", default=None,
                     help="In --bundle mode, suppress index.html (overrides config).")
    p.add_argument("--mermaid", choices=("auto", "mmdc", "kroki", "none"), default=None,
                   help="How to render mermaid diagrams to SVG (overrides config).")
    args = p.parse_args(argv)

    if args.setup:
        path, created = ensure_config()
        cfg = load_config()
        out = cfg.get("output_dir", DEFAULT_OUTPUT_DIR)
        resolved = os.path.expanduser(os.path.expandvars(out))
        emit_index = config_emit_index()
        mermaid = config_mermaid_mode()
        action = "Created" if created else "Found"
        print(f"herald: {action} config at {path}")
        print(f"  output_dir:  {out}")
        print(f"  resolves to: {resolved}")
        print(f"  emit_index:  {emit_index}")
        print(f"  mermaid:     {mermaid}")
        return 0

    if args.bundle and args.input:
        p.error("Pick one: <input> for single mode, or --bundle DIR for bundle mode.")
    if not args.bundle and not args.input:
        p.error("Need an input file or --bundle DIR (or --setup to configure).")

    # Auto-create config on first real use, but tell the user.
    _, created = ensure_config()
    if created:
        print(f"herald: created default config at {CONFIG_PATH} (output_dir: {DEFAULT_OUTPUT_DIR})",
              file=sys.stderr)

    if args.bundle:
        root = Path(args.bundle).resolve()
        if not root.is_dir():
            p.error(f"--bundle path is not a directory: {root}")
        out_dir = Path(args.out).resolve() if args.out else None
        emit_index = args.emit_index if args.emit_index is not None else config_emit_index()
        target_dir, written = render_bundle(
            root, out_dir, emit_index=emit_index, mermaid_mode=args.mermaid,
        )
        # Print one line per file written, ending with the dir for easy parsing.
        for path in written:
            print(path)
        if not emit_index:
            print(f"# {len(written)} report(s) written to {target_dir}", file=sys.stderr)
            print(f"# index.html skipped (set emit_index: true in {CONFIG_PATH} or pass --index to enable)",
                  file=sys.stderr)
        return 0

    input_path = Path(args.input).resolve()
    if not input_path.is_file():
        p.error(f"input not found: {input_path}")
    out_path = Path(args.out).resolve() if args.out else None
    path = render_one(input_path, out_path, mermaid_mode=args.mermaid)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
