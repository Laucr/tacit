#!/usr/bin/env node
// check_errors.js — detects ignored errors and poor error handling in Go files.
// Use: node check_errors.js file1.go file2.go ...
"use strict";

const fs = require("fs");

const IGNORED_SINGLE = /^\s*_\s*=\s*\w[\w.]*\s*\(/;
const IGNORED_DOUBLE = /^\s*\w+\s*,\s*_\s*:?=\s*\w[\w.]*\s*\(/;

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
  let inBlockComment = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed.startsWith("/*")) inBlockComment = true;
    if (inBlockComment) {
      if (trimmed.includes("*/")) inBlockComment = false;
      continue;
    }
    if (trimmed.startsWith("//")) continue;

    // _ = someFunc(...)
    if (IGNORED_SINGLE.test(line)) {
      if (line.includes("flag.") || line.includes("io.Discard")) continue;
      findings.push({
        file: filePath,
        line: i + 1,
        severity: "warning",
        check: "error_handling",
        message: "Error explicitly ignored with _ = pattern",
        code: trimmed,
      });
    }

    // val, _ = someFunc(...)
    if (IGNORED_DOUBLE.test(line)) {
      if (line.includes("range") || line.includes(".(")) continue;
      findings.push({
        file: filePath,
        line: i + 1,
        severity: "warning",
        check: "error_handling",
        message: "Second return value (likely error) ignored with _ pattern",
        code: trimmed,
      });
    }
  }
  return findings;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  process.stderr.write("Usage: node check_errors.js <file.go> ...\n");
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
