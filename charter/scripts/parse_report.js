#!/usr/bin/env node
// parse_report.js — extract actionable items from a scout drift report
// Use: node parse_report.js <report.md>
"use strict";

const fs = require("fs");
const path = require("path");

const reportPath = process.argv[2];

if (!reportPath) {
  process.stderr.write("Usage: node parse_report.js <report.md>\n");
  process.exit(1);
}

let content;
try {
  content = fs.readFileSync(reportPath, "utf8");
} catch (e) {
  process.stderr.write(`Cannot read report: ${reportPath}: ${e.message}\n`);
  process.exit(1);
}

const lines = content.split("\n");

/**
 * Extract metadata from the report header.
 */
function extractMeta() {
  let branch = "";
  let commit = "";
  let severity = "";
  let status = "";

  for (const line of lines) {
    const branchMatch = line.match(/^\*\*Branch:\*\*\s*(.+)/);
    if (branchMatch) branch = branchMatch[1].trim();

    const commitMatch = line.match(/^\*\*Commit:\*\*\s*(.+)/);
    if (commitMatch) commit = commitMatch[1].trim();

    const sevMatch = line.match(/^\*\*Overall severity:\*\*\s*(.+)/);
    if (sevMatch) severity = sevMatch[1].trim();

    const statusMatch = line.match(/^\*\*Status:\*\*\s*(.+)/);
    if (statusMatch) status = statusMatch[1].trim();
  }

  return { branch, commit, severity, status };
}

/**
 * Extract recommendations from the "Recommendations for Charter" section.
 * Each line is a markdown checkbox: - [ ] [TAG] description
 */
function extractRecommendations() {
  const updates = [];
  const smells = [];
  const undecided = [];

  let inRecommendations = false;

  for (const line of lines) {
    // Detect section start
    if (line.match(/^##\s+Recommendations for Charter/)) {
      inRecommendations = true;
      continue;
    }

    // Detect next section (end of recommendations)
    if (inRecommendations && line.match(/^##\s+/) && !line.match(/Recommendations/)) {
      break;
    }

    if (!inRecommendations) continue;

    const trimmed = line.trim();
    if (!trimmed.startsWith("- [")) continue;

    // Parse the checkbox line
    // Formats:
    //   - [ ] Update structural map: new package `pkg/newfeature`
    //   - [ ] [DECIDE] Error handling convention: ...
    //   - [ ] [UPDATE] Error handling convention: ...
    //   - [ ] [SMELL] Ignored error in ...

    // Extract the tag and action
    const tagMatch = trimmed.match(/^- \[[ x]\]\s+(?:\[(\w+)\]\s+)?(.+)$/);
    if (!tagMatch) continue;

    const tag = tagMatch[1] || "";
    const action = tagMatch[2].trim();

    // Determine category from the action text
    let category = "other";
    if (/structural|package/i.test(action)) category = "structural";
    else if (/convention|error.handling|logging|context|defer|naming/i.test(action)) category = "convention";
    else if (/dependency|dep/i.test(action)) category = "dependency";
    else if (/interface|export|symbol|signature/i.test(action)) category = "interface";

    const item = { category, action };

    if (tag === "UPDATE") {
      updates.push(item);
    } else if (tag === "SMELL") {
      smells.push(item);
    } else if (tag === "DECIDE") {
      undecided.push(item);
    } else {
      // No tag = straightforward update (structural, dep, interface changes without DECIDE)
      updates.push(item);
    }
  }

  return { updates, smells, undecided };
}

/**
 * Extract convention deviation details from the report tables.
 * Used to provide richer context for updates.
 */
function extractConventionDetails() {
  const details = [];
  let inConventionTable = false;
  let headerParsed = false;

  for (const line of lines) {
    if (line.match(/^##\s+Convention Deviations/)) {
      inConventionTable = true;
      continue;
    }

    if (inConventionTable && line.match(/^##\s+/) && !line.match(/Convention/)) {
      break;
    }

    if (!inConventionTable) continue;

    const trimmed = line.trim();

    // Skip table header and separator
    if (trimmed.startsWith("| #") || trimmed.startsWith("|---")) {
      headerParsed = true;
      continue;
    }

    if (!headerParsed || !trimmed.startsWith("|")) continue;

    // Parse table row: | # | Type | File | Line | Severity | Convention | Actual | Decision |
    const cells = trimmed.split("|").map(c => c.trim()).filter(Boolean);
    if (cells.length >= 7) {
      details.push({
        type: cells[1],
        file: cells[2],
        line: cells[3],
        severity: cells[4],
        convention: cells[5],
        actual: cells[6],
        decision: cells[7] || ""
      });
    }
  }

  return details;
}

/**
 * Extract structural change details from the report tables.
 */
function extractStructuralDetails() {
  const details = [];
  let inTable = false;
  let headerParsed = false;

  for (const line of lines) {
    if (line.match(/^##\s+Structural Changes/)) {
      inTable = true;
      continue;
    }

    if (inTable && line.match(/^##\s+/) && !line.match(/Structural/)) {
      break;
    }

    if (!inTable) continue;

    const trimmed = line.trim();

    if (trimmed.startsWith("| #") || trimmed.startsWith("|---")) {
      headerParsed = true;
      continue;
    }

    if (!headerParsed || !trimmed.startsWith("|")) continue;

    const cells = trimmed.split("|").map(c => c.trim()).filter(Boolean);
    if (cells.length >= 4) {
      details.push({
        type: cells[1],
        path: cells[2],
        severity: cells[3],
        description: cells[4] || ""
      });
    }
  }

  return details;
}

/**
 * Extract dependency change details.
 */
function extractDependencyDetails() {
  const details = [];
  let inTable = false;
  let headerParsed = false;

  for (const line of lines) {
    if (line.match(/^##\s+Dependency Changes/)) {
      inTable = true;
      continue;
    }

    if (inTable && line.match(/^##\s+/) && !line.match(/Dependency/)) {
      break;
    }

    if (!inTable) continue;

    const trimmed = line.trim();

    if (trimmed.startsWith("| #") || trimmed.startsWith("|---")) {
      headerParsed = true;
      continue;
    }

    if (!headerParsed || !trimmed.startsWith("|")) continue;

    const cells = trimmed.split("|").map(c => c.trim()).filter(Boolean);
    if (cells.length >= 5) {
      details.push({
        type: cells[1],
        package: cells[2],
        old_version: cells[3],
        new_version: cells[4],
        severity: cells[5] || ""
      });
    }
  }

  return details;
}

/**
 * Extract interface change details.
 */
function extractInterfaceDetails() {
  const details = [];
  let inTable = false;
  let headerParsed = false;

  for (const line of lines) {
    if (line.match(/^##\s+Interface Changes/)) {
      inTable = true;
      continue;
    }

    if (inTable && line.match(/^##\s+/) && !line.match(/Interface/)) {
      break;
    }

    if (!inTable) continue;

    const trimmed = line.trim();

    if (trimmed.startsWith("| #") || trimmed.startsWith("|---")) {
      headerParsed = true;
      continue;
    }

    if (!headerParsed || !trimmed.startsWith("|")) continue;

    const cells = trimmed.split("|").map(c => c.trim()).filter(Boolean);
    if (cells.length >= 5) {
      details.push({
        type: cells[1],
        package: cells[2],
        symbol: cells[3],
        severity: cells[4],
        description: cells[5] || ""
      });
    }
  }

  return details;
}

// ── Main ──

function run() {
  const meta = extractMeta();

  // If already applied, report and exit
  if (meta.status === "APPLIED") {
    process.stdout.write(JSON.stringify({
      report: path.basename(reportPath),
      status: "APPLIED",
      message: "This report has already been applied by charter."
    }, null, 2) + "\n");
    process.exit(0);
  }

  const { updates, smells, undecided } = extractRecommendations();

  const result = {
    report: path.basename(reportPath),
    branch: meta.branch,
    commit: meta.commit,
    severity: meta.severity,
    updates,
    smells,
    undecided,
    details: {
      structural: extractStructuralDetails(),
      convention: extractConventionDetails(),
      dependency: extractDependencyDetails(),
      interface: extractInterfaceDetails()
    }
  };

  process.stdout.write(JSON.stringify(result, null, 2) + "\n");

  // Exit 1 if there are undecided items
  process.exit(undecided.length > 0 ? 1 : 0);
}

run();
