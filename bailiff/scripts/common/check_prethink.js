#!/usr/bin/env node
// check_prethink.js — leftover narration of unchosen paths/plans in source.
// Rejected alternatives belong in the plan, not in comments or dead code.
// Use: node check_prethink.js [file-or-dir ...]
"use strict";

const path = require("path");
const { collectFiles, emit, finding, isGenerated, readLines } = require("./lib");

const SOURCE_EXT = new Set([
  ".go", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
  ".py", ".rb", ".rs", ".java", ".kt", ".kts",
  ".c", ".h", ".cc", ".cpp", ".hpp", ".cs",
  ".php", ".swift", ".scala", ".m", ".mm",
  ".sql", ".sh", ".bash", ".zsh", ".fish",
  ".vue", ".svelte", ".zig", ".lua", ".r", ".pl",
  ".ex", ".exs", ".erl", ".hs", ".proto", ".graphql",
  ".tf", ".toml",
]);

const SOURCE_NAMES = new Set(["Dockerfile", "Makefile", "CMakeLists.txt", "Gemfile", "Rakefile"]);

const HASH_COMMENT_EXT = new Set([
  ".py", ".sh", ".bash", ".zsh", ".fish", ".rb", ".pl", ".r",
  ".yaml", ".yml", ".tf", ".toml", ".ex", ".exs", ".jl",
]);
const SLASH_COMMENT_EXT = new Set([
  ".go", ".js", ".ts", ".jsx", ".tsx", ".mjs", ".cjs",
  ".java", ".kt", ".kts", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs",
  ".php", ".swift", ".scala", ".m", ".mm", ".rs", ".zig",
  ".proto", ".graphql", ".vue", ".svelte",
]);
const DASH_COMMENT_EXT = new Set([".sql", ".hs", ".lua"]);

const PHRASES = [
  { re: /\bwe (?:also )?could(?:'ve| have)? (?:also )?(?:used|gone with|tried|done|switched)\b/i, why: "narrates an unchosen approach" },
  { re: /\balternative(?:ly)?(?:[:,]|\s+(?:we|approach|implementation|plan|design|would))\b/i, why: "alternative-path leftover" },
  { re: /\banother (?:approach|option|plan|implementation) (?:would|is|was|we)\b/i, why: "alternative-path leftover" },
  { re: /\b(?:originally|initially) (?:i |we )?(?:wanted|planned|considered|thought|used|went)\b/i, why: "recaps a discarded plan" },
  { re: /\brejected (?:because|in favour|in favor|approach|plan)\b/i, why: "rejected-plan leftover" },
  { re: /\bunchosen (?:path|plan|approach|option)\b/i, why: "unchosen-path leftover" },
  { re: /\binstead of (?:using|the original|going with)\b/i, why: "compares to a discarded approach" },
  { re: /\bleftover from\b/i, why: "leftover from a prior approach" },
  { re: /\bnot (?:going )?with (?:the )?(?:original|other|first) (?:plan|approach|design)\b/i, why: "unchosen-plan leftover" },
  { re: /\bdecided not to (?:use|go with|implement)\b/i, why: "decision-rationale comment; belongs in the plan" },
  { re: /\bcould also have\b/i, why: "unchosen-path leftover" },
  { re: /\bthe other plan\b/i, why: "unchosen-plan leftover" },
  { re: /\bif we (?:had )?switched to\b/i, why: "hypothetical unused path" },
  { re: /\bkeeping this in case we\b/i, why: "dead code retained for a maybe-path" },
  { re: /\bold implementation\b/i, why: "old-implementation leftover" },
  { re: /\bwe considered\b/i, why: "recaps a discarded consideration" },
  { re: /\bfallback if we (?:switch|change|move)\b/i, why: "unused fallback for an unchosen path" },
  { re: /\bnot using \S+ because\b/i, why: "justifies an absence that belongs in the plan" },
];

const DEAD_GATE = /^\s*(?:if\s*\(\s*(?:false|0)\s*\)|if\s+False\s*:|if\s+false\s*(?:\{|$)|#if\s+0\b)/;

const CODEISH = /[{};]|=>|func\s|def\s|fn\s|class\s|return\s|import\s|const\s|let\s|var\s|if\s*\(|package\s|struct\s|typedef\s|public\s|private\s|endif\b|console\.(log|error)|fmt\.|os\./;

function isSource(rel) {
  const base = path.posix.basename(rel);
  if (SOURCE_NAMES.has(base)) return true;
  const ext = path.posix.extname(base).toLowerCase();
  return SOURCE_EXT.has(ext);
}

function extOf(rel) {
  return path.posix.extname(rel).toLowerCase();
}

function usesHashComments(rel, ext) {
  if (HASH_COMMENT_EXT.has(ext)) return true;
  return SOURCE_NAMES.has(path.posix.basename(rel));
}

function lineCommentText(line, rel) {
  const t = line.trim();
  const ext = extOf(rel);
  if (SLASH_COMMENT_EXT.has(ext)) {
    const m = t.match(/^\/\/\/?\s?(.*)$/);
    if (m) return m[1];
  }
  if (usesHashComments(rel, ext)) {
    const m = t.match(/^#\s?(.*)$/);
    if (m) return m[1];
  }
  if (DASH_COMMENT_EXT.has(ext)) {
    const m = t.match(/^--\s+(.*)$/) || t.match(/^--(.*)$/);
    if (m) return m[1];
  }
  const html = t.match(/^<!--\s?(.*?)(?:-->)?$/);
  if (html) return html[1];
  return null;
}

function looksLikeCode(text) {
  const s = text.trim();
  if (s.length < 8) return false;
  return CODEISH.test(s);
}

function scanComments(lines, rel) {
  const comments = []; // {line, text, isBlock}
  const ext = extOf(rel);
  const slash = SLASH_COMMENT_EXT.has(ext);
  const hash = usesHashComments(rel, ext);
  let inBlock = false;
  let inPythonDoc = false;
  let pyDelim = null;

  for (let i = 0; i < lines.length; i++) {
    const raw = lines[i];
    const t = raw.trim();

    if (inPythonDoc) {
      comments.push({ line: i + 1, text: t.replace(new RegExp(pyDelim, "g"), "").trim(), isBlock: true });
      if (t.includes(pyDelim)) {
        inPythonDoc = false;
        pyDelim = null;
      }
      continue;
    }

    if (inBlock) {
      const end = t.indexOf("*/");
      const text = (end >= 0 ? t.slice(0, end) : t).replace(/^\*+/, "").trim();
      comments.push({ line: i + 1, text, isBlock: true });
      if (end >= 0) inBlock = false;
      continue;
    }

    // Standalone python docstring, not an assignment like CSS = r"""...
    if (hash && /^["']{3}/.test(t) && !t.slice(3).includes(t.slice(0, 3))) {
      pyDelim = t.slice(0, 3);
      inPythonDoc = true;
      comments.push({ line: i + 1, text: t.slice(3).trim(), isBlock: true });
      continue;
    }

    if (slash) {
      const blockStart = t.indexOf("/*");
      if (blockStart === 0) {
        const after = t.slice(2);
        const end = after.indexOf("*/");
        if (end >= 0) {
          comments.push({ line: i + 1, text: after.slice(0, end).trim(), isBlock: true });
        } else {
          inBlock = true;
          comments.push({ line: i + 1, text: after.replace(/^\*+/, "").trim(), isBlock: true });
        }
        continue;
      }
      const inline = raw.match(/\/\/\s?(.*)$/);
      if (inline && !t.startsWith("//")) {
        comments.push({ line: i + 1, text: inline[1], isBlock: false });
        continue;
      }
    }

    const full = lineCommentText(raw, rel);
    if (full !== null) comments.push({ line: i + 1, text: full, isBlock: false });
  }
  return comments;
}

function checkFile(rel, content, lines) {
  if (isGenerated(content)) return [];
  if (!isSource(rel)) return [];
  const out = [];
  const comments = scanComments(lines, rel);

  for (const c of comments) {
    if (!c.text) continue;
    for (const p of PHRASES) {
      if (p.re.test(c.text)) {
        out.push(
          finding(
            rel,
            c.line,
            "warning",
            "prethink",
            `Redundant pre-thinking: ${p.why}. Keep the chosen path only; rejected options live in the plan.`,
            c.text.slice(0, 200)
          )
        );
        break;
      }
    }
  }

  // Consecutive commented-out code (≥5 comment lines that look like code).
  let run = [];
  const flush = () => {
    if (run.length >= 5 && run.filter((c) => looksLikeCode(c.text)).length >= 4) {
      out.push(
        finding(
          rel,
          run[0].line,
          "warning",
          "prethink",
          `Commented-out code block (${run.length} lines) — leftover from an unchosen path; delete it.`,
          run[0].text.slice(0, 200)
        )
      );
    }
    run = [];
  };
  let prevLine = 0;
  for (const c of comments) {
    if (c.isBlock) continue;
    if (prevLine && c.line !== prevLine + 1) flush();
    if (looksLikeCode(c.text) || (run.length && c.text === "")) {
      run.push(c);
      prevLine = c.line;
    } else {
      flush();
      prevLine = 0;
    }
  }
  flush();

  for (let i = 0; i < lines.length; i++) {
    if (DEAD_GATE.test(lines[i])) {
      out.push(
        finding(
          rel,
          i + 1,
          "warning",
          "prethink",
          "Dead gate (if false / #if 0) — unused path left in the code space.",
          lines[i].trim().slice(0, 200)
        )
      );
    }
  }
  return out;
}

function skipPath(rel) {
  // Plans/PRDs are supposed to record alternatives. Do not scan them.
  const p = rel.replace(/\\/g, "/");
  if (p.includes(".claude/prds/") || p.includes(".claude/plans/") || p.includes(".claude/reports/")) return true;
  if (p.includes(".claude/amendments/")) return true;
  return false;
}

function main(args, opts) {
  const { root, files } = collectFiles(args, { ...(opts || {}), skipPath });
  const findings = [];
  for (const rel of files) {
    if (!isSource(rel)) continue;
    const got = readLines(root, rel);
    if (!got) continue;
    findings.push(...checkFile(rel, got.content, got.lines));
  }
  return findings;
}

if (require.main === module) {
  emit(main(process.argv.slice(2)));
}

module.exports = { main, checkFile, isSource };
