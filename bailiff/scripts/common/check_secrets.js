#!/usr/bin/env node
// check_secrets.js — tokens, API keys, private keys, credentialed URLs,
// and other confidential literals in the code space, git-tracked files,
// and harness dirs (.claude, .agent, .agents).
// Use: node check_secrets.js [file-or-dir ...]
"use strict";

const { collectFiles, emit, finding, isGenerated, readLines } = require("./lib");

const REDACTED = "***REDACTED***";

const PLACEHOLDER_VALUE = /^(?:your[_-]?[\w-]*|my[_-]?[\w-]*|dummy|example|sample|placeholder|changeme|secret|password|passwd|token|key|xxx+|redacted|todo|insert|replace|null|none|undefined|changethis|not_a_secret|fake(?:[_-]?key)?|test(?:[_-]?key)?|<\w[\w.-]*>|\$\{[\w.-]+\}|\$[\w.-]+)$/i;

const SENSITIVE_KEY = /(?:api[_-]?key|apikey|auth[_-]?token|access[_-]?token|refresh[_-]?token|secret[_-]?key|client[_-]?secret|private[_-]?key|aws[_-]?secret|db[_-]?password|database[_-]?url|connection[_-]?string|password|passwd|\bpwd\b|token|secret)/i;

const TOKEN_PATTERNS = [
  { name: "private_key", re: /-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----/, severity: "error" },
  { name: "aws_access_key", re: /\bAKIA[0-9A-Z]{16}\b/, severity: "error" },
  { name: "github_pat", re: /\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b/, severity: "error" },
  { name: "github_fine_grained", re: /\bgithub_pat_[A-Za-z0-9_]{20,}\b/, severity: "error" },
  { name: "slack_token", re: /\bxox[baprs]-[A-Za-z0-9-]{10,}\b/, severity: "error" },
  { name: "openai_key", re: /\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b/, severity: "error" },
  { name: "stripe_live", re: /\b(?:sk|rk|pk)_live_[A-Za-z0-9]{16,}\b/, severity: "error" },
  { name: "google_api", re: /\bAIza[0-9A-Za-z_-]{35}\b/, severity: "error" },
  { name: "jwt", re: /\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/, severity: "warning" },
];

const CREDENTIAL_URL = /(?:[a-z][a-z0-9+.-]*):\/\/[^/\s:]+:[^@\s]+@/i;
const DOC_CREDENTIAL_URL = /:\/\/(?:user|username|role|name):(?:pass|password|pwd|secret)@/i;
const QUERY_SECRET = /[?&](?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password|passwd|signature|key)=([^&\s"'`]+)/i;
const PRIVATE_HOST = /(?:[a-z][a-z0-9+.-]*):\/\/(?:(?:10|127)\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|localhost|[^/\s"'`]+\.(?:internal|corp|lan|local))(?::\d+)?/i;

const PUBLIC_HOST_OK = /(?:example\.(?:com|org|net)|github\.com|gitlab\.com|bitbucket\.org|golang\.org|go\.dev|npmjs\.com|pypi\.org|wikipedia\.org|w3\.org|schema\.org|localhost|127\.0\.0\.1)/i;

const ASSIGN_RE = /(?:^|[\s,{])([A-Za-z_][\w.-]*)\s*[:=]\s*(["'`])([^"'`]{8,}?)\2/;
const ENV_RE = /^\s*(?:export\s+)?([A-Za-z_][\w]*)\s*=\s*(?:["']([^"']+)["']|([^\s#]+))/;

function looksPlaceholder(val) {
  const v = String(val).trim();
  if (v.length < 8) return true;
  if (PLACEHOLDER_VALUE.test(v)) return true;
  if (/^\$\{?[\w.:-]+\}?$/.test(v)) return true;
  if (/^(?:process\.env|os\.Getenv|os\.environ|ENV\[)/.test(v)) return true;
  if (/^<.*>$/.test(v)) return true;
  if (/^x+$/i.test(v) || /^\*+$/.test(v) || /^\.+$/.test(v)) return true;
  return false;
}

function redactLine(line) {
  let s = line;
  s = s.replace(/-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----[\s\S]*?-----END (?:[A-Z]+ )?PRIVATE KEY-----/g, `-----BEGIN PRIVATE KEY-----\n${REDACTED}\n-----END PRIVATE KEY-----`);
  s = s.replace(/\bAKIA[0-9A-Z]{16}\b/g, REDACTED);
  s = s.replace(/\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b/g, REDACTED);
  s = s.replace(/\bgithub_pat_[A-Za-z0-9_]{20,}\b/g, REDACTED);
  s = s.replace(/\bxox[baprs]-[A-Za-z0-9-]{10,}\b/g, REDACTED);
  s = s.replace(/\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b/g, REDACTED);
  s = s.replace(/\b(?:sk|rk|pk)_live_[A-Za-z0-9]{16,}\b/g, REDACTED);
  s = s.replace(/\bAIza[0-9A-Za-z_-]{35}\b/g, REDACTED);
  s = s.replace(/\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b/g, REDACTED);
  s = s.replace(/(:\/\/[^/\s:]+:)([^@\s]+)@/g, `$1${REDACTED}@`);
  s = s.replace(/([?&](?:api[_-]?key|access[_-]?token|auth[_-]?token|token|secret|password|passwd|signature|key)=)([^&\s"'`]+)/gi, `$1${REDACTED}`);
  s = s.replace(/(["'`])([^"'`]{8,})\1/g, (full, q, val) => {
    if (looksPlaceholder(val)) return full;
    if (val.length >= 12) return q + REDACTED + q;
    return full;
  });
  return s.slice(0, 220);
}

function push(out, rel, lineNo, severity, message, line) {
  out.push(finding(rel, lineNo, severity, "secrets", message, redactLine(line.trim())));
}

function checkFile(rel, content, lines) {
  if (isGenerated(content)) return [];
  const out = [];
  const seen = new Set();

  function add(lineNo, severity, message, line) {
    const key = `${lineNo}:${severity}:${message}`;
    if (seen.has(key)) return;
    seen.add(key);
    push(out, rel, lineNo, severity, message, line);
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (!trimmed) continue;

    for (const spec of TOKEN_PATTERNS) {
      if (spec.re.test(line)) {
        add(i + 1, spec.severity, `Confidential literal (${spec.name})`, line);
      }
      spec.re.lastIndex = 0;
    }

    if (CREDENTIAL_URL.test(line) && !DOC_CREDENTIAL_URL.test(line)) {
      add(i + 1, "error", "URL embeds user:password credentials", line);
    }
    CREDENTIAL_URL.lastIndex = 0;
    DOC_CREDENTIAL_URL.lastIndex = 0;

    const q = QUERY_SECRET.exec(line);
    if (q && !looksPlaceholder(q[1])) {
      add(i + 1, "error", "URL query string carries a secret parameter", line);
    }
    QUERY_SECRET.lastIndex = 0;

    if (PRIVATE_HOST.test(line) && !PUBLIC_HOST_OK.test(line)) {
      add(i + 1, "warning", "Hardcoded private/internal URL — move to config", line);
    }
    PRIVATE_HOST.lastIndex = 0;

    const env = ENV_RE.exec(trimmed);
    if (env && SENSITIVE_KEY.test(env[1])) {
      const quoted = env[2];
      const unquoted = env[3];
      const val = quoted || unquoted || "";
      const codey = !quoted && /[()[\]{}]|["']|\.\w+\(/.test(unquoted || "");
      if (!codey && !looksPlaceholder(val) && val.length >= 8) {
        add(i + 1, "error", `Sensitive assignment ${env[1]} has a literal value`, line);
      }
    }

    const as = ASSIGN_RE.exec(line);
    if (as && SENSITIVE_KEY.test(as[1])) {
      const val = as[3];
      if (!looksPlaceholder(val)) {
        add(i + 1, "error", `Sensitive assignment ${as[1]} has a literal value`, line);
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

module.exports = { main, checkFile, redactLine };
