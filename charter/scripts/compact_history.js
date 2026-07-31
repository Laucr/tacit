#!/usr/bin/env node
// compact_history.js — compact old drift reports to prevent unbounded growth
// Use: node compact_history.js <history-dir> [--threshold 10] [--keep-ratio 0.2]
"use strict";

const fs = require("fs");
const path = require("path");

const historyDir = process.argv[2];
let threshold = 10;
let keepRatio = 0.2;

// Parse optional flags
for (let i = 3; i < process.argv.length; i++) {
  if (process.argv[i] === "--threshold" && process.argv[i + 1]) {
    threshold = parseInt(process.argv[++i], 10);
  }
  if (process.argv[i] === "--keep-ratio" && process.argv[i + 1]) {
    keepRatio = parseFloat(process.argv[++i]);
  }
}

if (!historyDir) {
  process.stderr.write("Usage: node compact_history.js <history-dir> [--threshold 10] [--keep-ratio 0.2]\n");
  process.exit(1);
}

/**
 * List all drift report files (non-compacted, non-archive).
 * Returns sorted by name (which sorts by timestamp since format is {branch}-{hash}-{timestamp}.md).
 */
function listReports() {
  let files;
  try {
    files = fs.readdirSync(historyDir);
  } catch (e) {
    process.stderr.write(`Cannot read directory: ${historyDir}: ${e.message}\n`);
    return [];
  }

  return files
    .filter(f => f.endsWith(".md") && !f.startsWith("_"))
    .sort();
}

/**
 * Extract summary info from a drift report for compaction.
 */
function extractReportSummary(filePath) {
  let content;
  try {
    content = fs.readFileSync(filePath, "utf8");
  } catch {
    return null;
  }

  const lines = content.split("\n");
  let date = "";
  let commit = "";
  let severity = "";
  let status = "";
  let structural = 0;
  let convention = 0;
  let dependency = 0;
  let iface = 0;

  for (const line of lines) {
    const dateMatch = line.match(/^\*\*Date:\*\*\s*(.+)/);
    if (dateMatch) date = dateMatch[1].trim();

    const commitMatch = line.match(/^\*\*Commit:\*\*\s*(.+)/);
    if (commitMatch) commit = commitMatch[1].trim();

    const sevMatch = line.match(/^\*\*Overall severity:\*\*\s*(.+)/);
    if (sevMatch) severity = sevMatch[1].trim();

    const statusMatch = line.match(/^\*\*Status:\*\*\s*(.+)/);
    if (statusMatch) status = statusMatch[1].trim();

    // Parse summary table row for category totals
    // Format: | Structural | 2 | 1 | 0 | 3 |
    const structMatch = line.match(/\|\s*Structural\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|/);
    if (structMatch) structural = parseInt(structMatch[1], 10);

    const convMatch = line.match(/\|\s*Convention\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|/);
    if (convMatch) convention = parseInt(convMatch[1], 10);

    const depMatch = line.match(/\|\s*Dependency\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|/);
    if (depMatch) dependency = parseInt(depMatch[1], 10);

    const ifaceMatch = line.match(/\|\s*Interface\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*(\d+)\s*\|/);
    if (ifaceMatch) iface = parseInt(ifaceMatch[1], 10);
  }

  return {
    file: path.basename(filePath),
    date,
    commit,
    severity,
    status: status || "APPLIED",
    structural,
    convention,
    dependency,
    interface: iface
  };
}

/**
 * Detect recurring patterns across compacted summaries.
 * A pattern is "recurring" if it appears in 3+ reports.
 */
function detectRecurringPatterns(summaries) {
  const patterns = {};

  for (const s of summaries) {
    if (s.convention > 0) {
      patterns["convention drift"] = (patterns["convention drift"] || 0) + 1;
    }
    if (s.structural > 0) {
      patterns["structural changes"] = (patterns["structural changes"] || 0) + 1;
    }
    if (s.dependency > 0) {
      patterns["dependency changes"] = (patterns["dependency changes"] || 0) + 1;
    }
    if (s.interface > 0) {
      patterns["interface changes"] = (patterns["interface changes"] || 0) + 1;
    }
  }

  const recurring = [];
  for (const [pattern, count] of Object.entries(patterns)) {
    if (count >= 3) {
      recurring.push(`${pattern} (${count}/${summaries.length})`);
    }
  }

  return recurring;
}

/**
 * Generate the compacted file content.
 */
function generateCompactedContent(summaries, existingContent) {
  const now = new Date().toISOString().replace(/[-:]/g, "").slice(0, 13);
  const firstDate = summaries[0].date || "unknown";
  const lastDate = summaries[summaries.length - 1].date || "unknown";
  const recurring = detectRecurringPatterns(summaries);

  const lines = [];

  if (existingContent) {
    // Append to existing compacted file
    // Find the table and append rows
    const existingLines = existingContent.split("\n");
    let insertIndex = existingLines.length;

    // Find the last table row or "## Recurring Patterns" section
    for (let i = existingLines.length - 1; i >= 0; i--) {
      if (existingLines[i].match(/^##\s+Recurring Patterns/)) {
        insertIndex = i;
        break;
      }
      if (existingLines[i].startsWith("|") && !existingLines[i].startsWith("| #") && !existingLines[i].startsWith("|--")) {
        insertIndex = i + 1;
        break;
      }
    }

    // Build new rows
    const newRows = [];
    const existingRowCount = existingLines.filter(l => l.startsWith("|") && !l.startsWith("| #") && !l.startsWith("|--")).length;
    let rowNum = existingRowCount + 1;

    for (const s of summaries) {
      newRows.push(`| ${rowNum++} | ${s.date} | ${s.commit} | ${s.severity} | ${s.structural} | ${s.convention} | ${s.dependency} | ${s.interface} | ${s.status} |`);
    }

    // Remove old Recurring Patterns section and rebuild
    const cleanedLines = existingLines.filter(l => !l.match(/^##\s+Recurring Patterns/) && !l.startsWith("- ") || existingLines.indexOf(l) < insertIndex);

    // Insert new rows before Recurring Patterns
    cleanedLines.splice(insertIndex, 0, ...newRows);

    // Add updated recurring patterns
    cleanedLines.push("");
    cleanedLines.push("## Recurring Patterns");
    cleanedLines.push("");
    if (recurring.length > 0) {
      for (const p of recurring) {
        cleanedLines.push(`- ${p}`);
      }
    } else {
      cleanedLines.push("No recurring patterns detected.");
    }

    return cleanedLines.join("\n");
  }

  // New compacted file
  lines.push("# Compacted Drift History");
  lines.push("");
  lines.push(`Compacted on: ${now}`);
  lines.push(`Reports covered: ${summaries.length} reports from ${firstDate} to ${lastDate}`);
  lines.push("");
  lines.push("| # | Date | Commit | Severity | Structural | Convention | Dependency | Interface | Status |");
  lines.push("|---|------|--------|----------|------------|------------|------------|-----------|--------|");

  summaries.forEach((s, i) => {
    lines.push(`| ${i + 1} | ${s.date} | ${s.commit} | ${s.severity} | ${s.structural} | ${s.convention} | ${s.dependency} | ${s.interface} | ${s.status} |`);
  });

  lines.push("");
  lines.push("## Recurring Patterns");
  lines.push("");

  if (recurring.length > 0) {
    for (const p of recurring) {
      lines.push(`- ${p}`);
    }
  } else {
    lines.push("No recurring patterns detected.");
  }

  return lines.join("\n");
}

// ── Main ──

function run() {
  const reports = listReports();

  if (reports.length <= threshold) {
    process.stdout.write(JSON.stringify({
      compacted: 0,
      kept: reports.length,
      compacted_file: null,
      recurring_patterns: [],
      message: `${reports.length} reports found, threshold is ${threshold}. No compaction needed.`
    }, null, 2) + "\n");
    process.exit(0);
  }

  // Calculate split point
  const keepCount = Math.max(1, Math.ceil(reports.length * keepRatio));
  const compactCount = reports.length - keepCount;

  const toCompact = reports.slice(0, compactCount);
  const toKeep = reports.slice(compactCount);

  // Extract summaries from reports to compact
  const summaries = [];
  for (const file of toCompact) {
    const filePath = path.join(historyDir, file);
    const summary = extractReportSummary(filePath);
    if (summary) {
      summaries.push(summary);
    }
  }

  if (summaries.length === 0) {
    process.stderr.write("No valid reports to compact.\n");
    process.exit(1);
  }

  // Generate compacted file
  const now = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  const compactedFileName = `_compacted-${now}.md`;
  const compactedFilePath = path.join(historyDir, compactedFileName);

  let existingContent = null;
  try {
    existingContent = fs.readFileSync(compactedFilePath, "utf8");
  } catch {
    // File doesn't exist yet
  }

  const compactedContent = generateCompactedContent(summaries, existingContent);

  // Write compacted file
  try {
    fs.writeFileSync(compactedFilePath, compactedContent, "utf8");
  } catch (e) {
    process.stderr.write(`Failed to write compacted file: ${e.message}\n`);
    process.exit(1);
  }

  // Delete compacted reports
  for (const file of toCompact) {
    try {
      fs.unlinkSync(path.join(historyDir, file));
    } catch (e) {
      process.stderr.write(`Warning: failed to delete ${file}: ${e.message}\n`);
    }
  }

  const recurring = detectRecurringPatterns(summaries);

  process.stdout.write(JSON.stringify({
    compacted: compactCount,
    kept: keepCount,
    compacted_file: compactedFileName,
    recurring_patterns: recurring,
    kept_files: toKeep
  }, null, 2) + "\n");

  process.exit(0);
}

run();
