#!/usr/bin/env node
// check_context.js — detects context propagation issues in Go files.
// Use: node check_context.js file1.go file2.go ...
"use strict";

const fs = require("fs");

const FUNC_WITH_CTX = /func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\([^)]*ctx\s+context\.Context/;
const BG_CTX = /context\.Background\(\)/;
const TODO_CTX = /context\.TODO\(\)/;

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

  // Pass 1: find functions that accept ctx and their ranges
  const funcs = [];
  let current = null;
  let braceDepth = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const m = FUNC_WITH_CTX.exec(line);
    if (m) {
      current = { name: m[1], start: i, end: -1 };
      braceDepth = 0;
    }

    if (current) {
      const opens = (line.match(/{/g) || []).length;
      const closes = (line.match(/}/g) || []).length;
      braceDepth += opens - closes;
      if (braceDepth <= 0 && i > current.start) {
        current.end = i;
        funcs.push(current);
        current = null;
      }
    }
  }

  // Pass 2: check for context.Background() inside functions that have ctx
  for (const fn of funcs) {
    for (let i = fn.start; i <= fn.end && i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();
      if (trimmed.startsWith("//")) continue;

      if (BG_CTX.test(line)) {
        findings.push({
          file: filePath,
          line: i + 1,
          severity: "warning",
          check: "context",
          message: `context.Background() inside ${fn.name}() which already has ctx parameter — use ctx instead`,
          code: trimmed,
        });
      }
    }
  }

  // Pass 3: check for context.TODO() outside test files
  for (let i = 0; i < lines.length; i++) {
    const trimmed = lines[i].trim();
    if (trimmed.startsWith("//")) continue;

    if (TODO_CTX.test(lines[i])) {
      findings.push({
        file: filePath,
        line: i + 1,
        severity: isTest ? "info" : "warning",
        check: "context",
        message: isTest
          ? "context.TODO() in test file — acceptable but consider context.Background()"
          : "context.TODO() found — replace with a real context or ctx parameter",
        code: trimmed,
      });
    }
  }

  return findings;
}

const files = process.argv.slice(2);
if (files.length === 0) {
  process.stderr.write("Usage: node check_context.js <file.go> ...\n");
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
