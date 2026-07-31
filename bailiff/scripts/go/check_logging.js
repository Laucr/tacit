#!/usr/bin/env node
// check_logging.js — detects fmt.Print/Println/Printf usage in Go files.
// Use: node check_logging.js file1.go file2.go ...
"use strict";

const fs = require("fs");
const path = require("path");

const FMT_PRINT_RE = /\bfmt\.(Println|Print|Printf)\s*\(/;

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

  const isTest = filePath.endsWith("_test.go");
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

    if (FMT_PRINT_RE.test(line)) {
      findings.push({
        file: filePath,
        line: i + 1,
        severity: isTest ? "info" : "warning",
        check: "logging",
        message: "fmt.Print/Println/Printf found — use log package instead",
        code: trimmed,
      });
    }
  }
  return findings;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  process.stderr.write("Usage: node check_logging.js <file.go> ...\n");
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
