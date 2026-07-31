#!/usr/bin/env node
// detect_conventions.js — detect convention deviations in changed Go files
// Use: node detect_conventions.js <rules.mdc> <file1.go> [file2.go ...]
"use strict";

const fs = require("fs");
const path = require("path");

const rulesFile = process.argv[2];
const goFiles = process.argv.slice(3);

if (!rulesFile || goFiles.length === 0) {
  process.stderr.write("Usage: node detect_conventions.js <rules.mdc> <file1.go> [file2.go ...]\n");
  process.exit(1);
}

/**
 * Parse the .mdc rules file to extract convention patterns.
 * Returns an object with convention categories and their expected patterns.
 */
function parseRules(filePath) {
  let content;
  try {
    content = fs.readFileSync(filePath, "utf8");
  } catch (e) {
    process.stderr.write(`Cannot read rules file: ${filePath}: ${e.message}\n`);
    process.exit(1);
  }

  // Strip YAML frontmatter
  const fmMatch = content.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/);
  const body = fmMatch ? fmMatch[1] : content;

  const rules = {
    error_handling: [],
    logging: [],
    context: [],
    defer_cleanup: [],
    naming: [],
    type_definition: []
  };

  // Extract error handling conventions
  const errorPatterns = body.match(/error[s]?\s+(?:handling|wrapping|propagat)[^\n]*/gi) || [];
  for (const p of errorPatterns) {
    rules.error_handling.push(p.trim());
  }

  // Extract logging conventions
  const logPatterns = body.match(/log(?:ging|ger)?[^\n]*/gi) || [];
  for (const p of logPatterns) {
    rules.logging.push(p.trim());
  }

  // Extract context conventions
  const ctxPatterns = body.match(/context\.?[^\n]*/gi) || [];
  for (const p of ctxPatterns) {
    rules.context.push(p.trim());
  }

  // Extract defer/cleanup conventions
  const deferPatterns = body.match(/defer[^\n]*/gi) || [];
  for (const p of deferPatterns) {
    rules.defer_cleanup.push(p.trim());
  }

  return { rules, raw: body };
}

/**
 * Check if a file is generated code.
 */
function isGenerated(lines) {
  for (let i = 0; i < Math.min(lines.length, 5); i++) {
    if (lines[i].includes("Code generated") || lines[i].includes("DO NOT EDIT")) {
      return true;
    }
  }
  return false;
}

/**
 * Check if a line is inside a comment block.
 */
function isComment(line) {
  const trimmed = line.trim();
  return trimmed.startsWith("//") || trimmed.startsWith("/*") || trimmed.startsWith("*");
}

// ── Convention checkers ──

/**
 * Detect error handling patterns and compare against conventions.
 */
function checkErrorHandling(filePath, lines, rulesRaw) {
  const findings = [];

  // Detect which error wrapping pattern is used
  const usesErrorsWrap = /errors\.Wrap\s*\(/;
  const usesFmtErrorf = /fmt\.Errorf\s*\([^)]*%w/;
  const usesErrorsNew = /errors\.New\s*\(/;
  const ignoresError = /^\s*_\s*=\s*\w[\w.]*\s*\(/;
  const ignoresSecond = /^\s*\w+\s*,\s*_\s*:?=\s*\w[\w.]*\s*\(/;

  // Check what the rules say about error wrapping
  const rulesPreferWrap = rulesRaw.match(/errors\.Wrap/i);
  const rulesPreferFmtErrorf = rulesRaw.match(/fmt\.Errorf.*%w/i);

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (isComment(line)) continue;

    // Check for ignored errors
    if (ignoresError.test(line) || ignoresSecond.test(line)) {
      // Skip flag.* and common intentional discards
      if (/flag\./.test(line) || /io\.Discard/.test(line)) continue;
      findings.push({
        category: "convention",
        type: "error_handling",
        severity: "medium",
        file: filePath,
        line: i + 1,
        convention: "Handle all errors",
        actual: line.trim(),
        message: "Error ignored — convention requires explicit error handling"
      });
    }

    // Detect wrapping style mismatch
    if (rulesPreferFmtErrorf && usesErrorsWrap.test(line)) {
      findings.push({
        category: "convention",
        type: "error_handling",
        severity: "medium",
        file: filePath,
        line: i + 1,
        convention: "fmt.Errorf(\"...: %w\", err)",
        actual: "errors.Wrap(...)",
        message: "Error wrapping uses errors.Wrap but convention specifies fmt.Errorf with %w"
      });
    } else if (rulesPreferWrap && usesFmtErrorf.test(line)) {
      findings.push({
        category: "convention",
        type: "error_handling",
        severity: "medium",
        file: filePath,
        line: i + 1,
        convention: "errors.Wrap(err, \"context\")",
        actual: "fmt.Errorf(\"...: %w\", err)",
        message: "Error wrapping uses fmt.Errorf but convention specifies errors.Wrap"
      });
    }
  }

  return findings;
}

/**
 * Detect logging pattern deviations.
 */
function checkLogging(filePath, lines, rulesRaw) {
  const findings = [];

  const fmtPrint = /\bfmt\.(Println|Print|Printf)\s*\(/;
  const isTestFile = filePath.endsWith("_test.go");

  // Detect which logger the rules prefer
  const rulesPreferZap = /\bzap\b/i.test(rulesRaw);
  const rulesPreferLogrus = /\blogrus\b/i.test(rulesRaw);
  const rulesPreferSlog = /\bslog\b/i.test(rulesRaw);
  const rulesPreferLog = /\blog\./.test(rulesRaw);

  // Track which loggers are used in this file
  const usesZap = /\bzap\.\w+/.test(lines.join("\n"));
  const usesLogrus = /\blogrus\.\w+/.test(lines.join("\n"));
  const usesSlog = /\bslog\.\w+/.test(lines.join("\n"));
  const usesStdLog = /\blog\.(Print|Fatal|Panic)/.test(lines.join("\n"));

  let inBlockComment = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    if (trimmed.includes("/*")) inBlockComment = true;
    if (trimmed.includes("*/")) { inBlockComment = false; continue; }
    if (inBlockComment || trimmed.startsWith("//")) continue;

    // fmt.Print* in non-test code
    if (fmtPrint.test(line) && !isTestFile) {
      findings.push({
        category: "convention",
        type: "logging",
        severity: "medium",
        file: filePath,
        line: i + 1,
        convention: "Use structured logger",
        actual: "fmt.Print*",
        message: "fmt.Print used instead of structured logger"
      });
    }

    // Wrong logger library
    if (rulesPreferZap && (usesLogrus || usesSlog || usesStdLog) && !usesZap) {
      // Only report once per file
      if (i === 0) {
        const actual = usesLogrus ? "logrus" : usesSlog ? "slog" : "log";
        findings.push({
          category: "convention",
          type: "logging",
          severity: "medium",
          file: filePath,
          line: 1,
          convention: "Use zap logger",
          actual: `Uses ${actual}`,
          message: `File uses ${actual} but convention specifies zap`
        });
      }
    } else if (rulesPreferLogrus && (usesZap || usesSlog || usesStdLog) && !usesLogrus) {
      if (i === 0) {
        const actual = usesZap ? "zap" : usesSlog ? "slog" : "log";
        findings.push({
          category: "convention",
          type: "logging",
          severity: "medium",
          file: filePath,
          line: 1,
          convention: "Use logrus logger",
          actual: `Uses ${actual}`,
          message: `File uses ${actual} but convention specifies logrus`
        });
      }
    }
  }

  return findings;
}

/**
 * Detect context propagation issues.
 */
function checkContext(filePath, lines, rulesRaw) {
  const findings = [];

  const funcWithCtx = /func\s+(?:\(\w+\s+\*?\w+\)\s+)?(\w+)\s*\([^)]*ctx\s+context\.Context/;
  const bgCtx = /context\.Background\(\)/;
  const todoCtx = /context\.TODO\(\)/;
  const isTestFile = filePath.endsWith("_test.go");

  let inCtxFunc = false;
  let braceDepth = 0;
  let funcName = "";

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (isComment(line)) continue;

    const funcMatch = line.match(funcWithCtx);
    if (funcMatch) {
      inCtxFunc = true;
      braceDepth = 0;
      funcName = funcMatch[1];
    }

    if (inCtxFunc) {
      for (const ch of line) {
        if (ch === "{") braceDepth++;
        if (ch === "}") braceDepth--;
      }

      // context.Background() inside a function that already has ctx
      if (bgCtx.test(line)) {
        findings.push({
          category: "convention",
          type: "context",
          severity: "medium",
          file: filePath,
          line: i + 1,
          convention: "Use provided ctx parameter",
          actual: "context.Background()",
          message: `context.Background() used inside ${funcName} which already has ctx parameter`
        });
      }

      if (braceDepth <= 0) {
        inCtxFunc = false;
      }
    }

    // context.TODO() in non-test code
    if (todoCtx.test(line) && !isTestFile) {
      findings.push({
        category: "convention",
        type: "context",
        severity: "low",
        file: filePath,
        line: i + 1,
        convention: "Propagate context explicitly",
        actual: "context.TODO()",
        message: "context.TODO() found in production code"
      });
    }
  }

  return findings;
}

/**
 * Detect defer/cleanup pattern issues.
 */
function checkDefer(filePath, lines, rulesRaw) {
  const findings = [];

  const ctxCancel = /(\w+)\s*,\s*(\w+)\s*:=\s*context\.With(Cancel|Timeout|Deadline)\s*\(/;
  const fileOpen = /(\w+)\s*,\s*\w+\s*:=\s*os\.(Open|Create|OpenFile)\s*\(/;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (isComment(line)) continue;

    // Context cancel check
    const ctxMatch = line.match(ctxCancel);
    if (ctxMatch) {
      const cancelVar = ctxMatch[2];
      let foundDefer = false;
      for (let j = i + 1; j < Math.min(i + 6, lines.length); j++) {
        if (lines[j].includes(`defer ${cancelVar}()`)) {
          foundDefer = true;
          break;
        }
      }
      if (!foundDefer) {
        findings.push({
          category: "convention",
          type: "defer",
          severity: "high",
          file: filePath,
          line: i + 1,
          convention: "defer cancel() after context.With*",
          actual: `Missing defer ${cancelVar}()`,
          message: `context.With${ctxMatch[3]} without defer ${cancelVar}() — potential context leak`
        });
      }
    }

    // File handle check
    const fileMatch = line.match(fileOpen);
    if (fileMatch) {
      const fileVar = fileMatch[1];
      let foundDefer = false;
      for (let j = i + 1; j < Math.min(i + 11, lines.length); j++) {
        if (lines[j].includes(`defer`) && lines[j].includes(`Close()`)) {
          foundDefer = true;
          break;
        }
        if (lines[j].includes(`${fileVar}.Close()`)) {
          foundDefer = true;
          break;
        }
      }
      if (!foundDefer) {
        findings.push({
          category: "convention",
          type: "defer",
          severity: "medium",
          file: filePath,
          line: i + 1,
          convention: "defer Close() after os.Open*",
          actual: `Missing defer ${fileVar}.Close()`,
          message: `os.${fileMatch[2]} without defer Close() — potential resource leak`
        });
      }
    }
  }

  return findings;
}

/**
 * Detect naming convention deviations.
 */
function checkNaming(filePath, lines, rulesRaw) {
  const findings = [];

  // Check for receiver naming conventions
  // Go convention: short, 1-2 char receiver names
  const receiverFunc = /func\s+\((\w+)\s+\*?(\w+)\)\s+(\w+)/;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (isComment(line)) continue;

    const match = line.match(receiverFunc);
    if (match) {
      const receiver = match[1];
      const typeName = match[2];
      // Check if receiver is too long (>3 chars is unusual for Go)
      if (receiver.length > 3 && receiver !== "self" && receiver !== "this") {
        findings.push({
          category: "convention",
          type: "naming",
          severity: "low",
          file: filePath,
          line: i + 1,
          convention: "Short receiver names (1-2 chars)",
          actual: `Receiver name: ${receiver}`,
          message: `Long receiver name "${receiver}" for type ${typeName} — Go convention is 1-2 chars`
        });
      }
    }
  }

  return findings;
}

// ── Main ──

function run() {
  const { rules, raw } = parseRules(rulesFile);
  let hasFindings = false;

  for (const filePath of goFiles) {
    if (!fs.existsSync(filePath)) continue;

    let content;
    try {
      content = fs.readFileSync(filePath, "utf8");
    } catch {
      continue;
    }

    const lines = content.split("\n");
    if (isGenerated(lines)) continue;

    const checks = [
      ...checkErrorHandling(filePath, lines, raw),
      ...checkLogging(filePath, lines, raw),
      ...checkContext(filePath, lines, raw),
      ...checkDefer(filePath, lines, raw),
      ...checkNaming(filePath, lines, raw)
    ];

    for (const finding of checks) {
      hasFindings = true;
      process.stdout.write(JSON.stringify(finding) + "\n");
    }
  }

  process.exit(hasFindings ? 1 : 0);
}

run();
