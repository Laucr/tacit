#!/usr/bin/env node
// check_defer.js — detects missing deferred cleanup for contexts and resources in Go files.
// Use: node check_defer.js file1.go file2.go ...
"use strict";

const fs = require("fs");

const CTX_CANCEL = /(\w+)\s*,\s*(\w+)\s*:=\s*context\.With(Cancel|Timeout|Deadline)\s*\(/;
const FILE_OPEN = /(\w+)\s*,\s*\w+\s*:=\s*os\.(Open|Create|OpenFile)\s*\(/;

function isGenerated(lines) {
  for (let i = 0; i < Math.min(5, lines.length); i++) {
    if (lines[i].includes("Code generated")) return true;
  }
  return false;
}

function check(filePath) {
  const content = fs.readFileSync(filePath, "utf8");
  const lines = content.split("\n");
  if (isGenerated(lines)) return [];

  const findings = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    if (trimmed.startsWith("//")) continue;

    // Check 1: context.WithCancel/Timeout/Deadline without defer cancel()
    const ctxMatch = CTX_CANCEL.exec(line);
    if (ctxMatch) {
      const cancelVar = ctxMatch[2];
      const kind = ctxMatch[3];
      let found = false;
      for (let j = i + 1; j < lines.length && j <= i + 5; j++) {
        if (lines[j].includes(`defer ${cancelVar}()`)) {
          found = true;
          break;
        }
      }
      if (!found) {
        findings.push({
          file: filePath,
          line: i + 1,
          severity: "error",
          check: "defer",
          message: `context.With${kind}() without defer ${cancelVar}() — context will leak`,
          code: trimmed,
        });
      }
    }

    // Check 2: os.Open/Create/OpenFile without defer Close()
    const fileMatch = FILE_OPEN.exec(line);
    if (fileMatch) {
      const fileVar = fileMatch[1];
      const method = fileMatch[2];
      let found = false;
      for (let j = i + 1; j < lines.length && j <= i + 10; j++) {
        if (
          lines[j].includes(`defer ${fileVar}.Close()`) ||
          lines[j].includes(`${fileVar}.Close()`)
        ) {
          found = true;
          break;
        }
      }
      if (!found) {
        findings.push({
          file: filePath,
          line: i + 1,
          severity: "warning",
          check: "defer",
          message: `os.${method}() without defer ${fileVar}.Close() — file handle may leak`,
          code: trimmed,
        });
      }
    }
  }

  return findings;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  process.stderr.write("Usage: node check_defer.js <file.go> ...\n");
  process.exit(1);
}

let hasFindings = false;
for (const f of files) {
  if (!fs.existsSync(f)) continue;
  for (const finding of check(f)) {
    hasFindings = true;
    process.stdout.write(JSON.stringify(finding) + "\n");
  }
}
process.exit(hasFindings ? 1 : 0);
