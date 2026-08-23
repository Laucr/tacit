#!/usr/bin/env node
// check_local_paths.js — machine-local filesystem paths leaked into the tree.
// Use: node check_local_paths.js [file-or-dir ...]
// No args: git-tracked files + .claude/.agent/.agents
"use strict";

const { collectFiles, emit, finding, isGenerated, readLines } = require("./lib");

// FHS / container / toolchain prefixes that are portable, not a developer machine.
const PORTABLE_PREFIX = /^(?:\/(?:usr|bin|sbin|lib|lib64|proc|sys|dev|etc|run|boot|opt\/(?:local)(?:\/|$)|var\/(?:log|run|tmp|lib|cache|spool)|tmp|app|src|workspace|work|go\/(?:src|pkg|bin)|nix\/store|proc)(?:\/|$)|\/$)/;

const PATTERNS = [
  {
    // macOS / Linux home directories
    re: /(^|[^A-Za-z0-9_])(\/(?:Users|home)\/[A-Za-z0-9._-]+(?:\/[^\s"'`\\]*)?)/g,
    kind: "home_path",
  },
  {
    // Windows user profile
    re: /(^|[^A-Za-z0-9_])([A-Za-z]:\\Users\\[^\s"'`]+)/g,
    kind: "windows_home",
  },
  {
    // Windows UNC
    re: /(^|[^A-Za-z0-9_])(\\\\[A-Za-z0-9._-]+\\[^\s"'`]+)/g,
    kind: "unc_path",
  },
  {
    // macOS per-user temp
    re: /(^|[^A-Za-z0-9_])(\/var\/folders\/[A-Za-z0-9_/+-]+)/g,
    kind: "macos_temp",
  },
  {
    // file:// URLs pointing at a home dir
    re: /(file:\/\/\/(?:Users|home)\/[A-Za-z0-9._-]+[^\s"'`]*)/g,
    kind: "file_url",
    noPrefix: true,
  },
  {
    // Apple Silicon Homebrew — machine-local toolchain
    re: /(^|[^A-Za-z0-9_])(\/opt\/homebrew\/[^\s"'`]*)/g,
    kind: "homebrew",
  },
  {
    // /root/<something> other than a bare mention of /root
    re: /(^|[^A-Za-z0-9_])(\/root\/[A-Za-z0-9._-]+[^\s"'`]*)/g,
    kind: "root_home",
  },
];

const PLACEHOLDER_USER = /^(?:user|username|name|you|someone|me|foo|bar|baz|alice|bob|chloe|example|placeholder|xxx+|path|to|project|repo|app)$/i;
const PLACEHOLDER_PATH = /\/(?:path\/to|your[-_]?project|your[-_]?user|username|example)(?:\/|$)/i;

function redactPath(p) {
  return p
    .replace(/(\/(?:Users|home)\/)([^/]+)/g, "$1***")
    .replace(/([A-Za-z]:\\Users\\)([^\\]+)/g, "$1***")
    .replace(/(\/root\/)([^/]+)/g, "$1***")
    .replace(/(file:\/\/\/(?:Users|home)\/)([^/]+)/g, "$1***");
}

function userFromHome(p) {
  const m = p.match(/\/(?:Users|home)\/([^/]+)/) || p.match(/\\Users\\([^\\]+)/) || p.match(/\/root\/([^/]+)/);
  return m ? m[1] : "";
}

function isPortable(p) {
  if (p.startsWith("/opt/homebrew")) return false;
  if (p.startsWith("/root/")) return false;
  if (p.startsWith("/Users/") || p.startsWith("/home/")) return false;
  if (/^[A-Za-z]:\\Users\\/.test(p)) return false;
  if (p.startsWith("/var/folders/")) return false;
  if (p.startsWith("file://")) return false;
  if (p.startsWith("\\\\")) return false;
  return PORTABLE_PREFIX.test(p);
}

function checkFile(rel, content, lines) {
  if (isGenerated(content)) return [];
  const out = [];
  const seen = new Set();
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    for (const spec of PATTERNS) {
      spec.re.lastIndex = 0;
      let m;
      while ((m = spec.re.exec(line)) !== null) {
        const raw = spec.noPrefix ? m[1] : m[2];
        if (!raw) continue;
        if (isPortable(raw)) continue;
        if (PLACEHOLDER_PATH.test(raw)) continue;
        const user = userFromHome(raw);
        if (user && PLACEHOLDER_USER.test(user)) continue;
        const key = `${i + 1}:${spec.kind}:${raw}`;
        if (seen.has(key)) continue;
        seen.add(key);
        out.push(
          finding(
            rel,
            i + 1,
            "warning",
            "local_paths",
            `Machine-local ${spec.kind.replace(/_/g, " ")} — replace with a relative path or config: ${redactPath(raw)}`,
            redactPath(line.trim()).slice(0, 200)
          )
        );
      }
    }
  }
  return out;
}

function main(args, opts) {
  const { root, files } = collectFiles(args, opts);
  const findings = [];
  for (const rel of files) {
    const got = readLines(root, rel);
    if (!got) continue;
    findings.push(...checkFile(rel, got.content, got.lines));
  }
  return findings;
}

if (require.main === module) {
  emit(main(process.argv.slice(2)));
}

module.exports = { main, checkFile };
