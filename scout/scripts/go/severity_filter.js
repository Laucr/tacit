#!/usr/bin/env node
// severity_filter.js — combine detection outputs, assess severity, generate markdown report
// Use: cat phase1.json phase2.json ... | node severity_filter.js [--branch <name>] [--hash <hash>] [--old-hash <hash>] [--date <iso>]
"use strict";

const fs = require("fs");

// Parse CLI flags
const args = process.argv.slice(2);
let branch = "main";
let hash = "unknown";
let oldHash = "unknown";
let date = new Date().toISOString().replace(/[-:]/g, "").slice(0, 13);

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--branch" && args[i + 1]) { branch = args[++i]; continue; }
  if (args[i] === "--hash" && args[i + 1]) { hash = args[++i]; continue; }
  if (args[i] === "--old-hash" && args[i + 1]) { oldHash = args[++i]; continue; }
  if (args[i] === "--date" && args[i + 1]) { date = args[++i]; continue; }
}

/**
 * Read all JSON lines from stdin.
 */
function readFindings() {
  let input;
  try {
    input = fs.readFileSync(0, "utf8");
  } catch {
    return [];
  }

  return input
    .trim()
    .split("\n")
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(Boolean);
}

/**
 * Determine overall severity based on findings.
 */
function assessOverallSeverity(findings) {
  let highCount = 0;
  let mediumCount = 0;
  let lowCount = 0;

  for (const f of findings) {
    if (f.severity === "high") highCount++;
    else if (f.severity === "medium") mediumCount++;
    else lowCount++;
  }

  if (highCount > 0) return "significant";
  if (mediumCount > 5 || findings.length > 10) return "moderate";
  if (mediumCount > 0) return "moderate";
  return "minor";
}

/**
 * Group findings by category.
 */
function groupByCategory(findings) {
  const groups = {
    structural: [],
    convention: [],
    dependency: [],
    interface: []
  };

  for (const f of findings) {
    if (groups[f.category]) {
      groups[f.category].push(f);
    }
  }

  return groups;
}

/**
 * Count severities per category.
 */
function severityCounts(findings) {
  let low = 0, medium = 0, high = 0;
  for (const f of findings) {
    if (f.severity === "low") low++;
    else if (f.severity === "medium") medium++;
    else if (f.severity === "high") high++;
  }
  return { low, medium, high, total: low + medium + high };
}

/**
 * Generate the markdown report.
 */
function generateReport(findings) {
  const groups = groupByCategory(findings);
  const overall = assessOverallSeverity(findings);

  const sCounts = severityCounts(groups.structural);
  const cCounts = severityCounts(groups.convention);
  const dCounts = severityCounts(groups.dependency);
  const iCounts = severityCounts(groups.interface);
  const tCounts = severityCounts(findings);

  const lines = [];

  // Header
  lines.push("# Scout Drift Report");
  lines.push("");
  lines.push(`**Branch:** ${branch}`);
  lines.push(`**Commit:** ${hash}`);
  lines.push(`**Previous:** ${oldHash}`);
  lines.push(`**Date:** ${date}`);
  lines.push(`**Overall severity:** ${overall}`);
  lines.push("");

  // Summary table
  lines.push("## Summary");
  lines.push("");
  lines.push("| Category | Low | Medium | High | Total |");
  lines.push("|----------|-----|--------|------|-------|");
  lines.push(`| Structural | ${sCounts.low} | ${sCounts.medium} | ${sCounts.high} | ${sCounts.total} |`);
  lines.push(`| Convention | ${cCounts.low} | ${cCounts.medium} | ${cCounts.high} | ${cCounts.total} |`);
  lines.push(`| Dependency | ${dCounts.low} | ${dCounts.medium} | ${dCounts.high} | ${dCounts.total} |`);
  lines.push(`| Interface | ${iCounts.low} | ${iCounts.medium} | ${iCounts.high} | ${iCounts.total} |`);
  lines.push(`| **Total** | **${tCounts.low}** | **${tCounts.medium}** | **${tCounts.high}** | **${tCounts.total}** |`);
  lines.push("");

  // Structural changes
  if (groups.structural.length > 0) {
    lines.push("## Structural Changes");
    lines.push("");
    lines.push("| # | Type | Path | Severity | Description |");
    lines.push("|---|------|------|----------|-------------|");
    groups.structural.forEach((f, i) => {
      lines.push(`| ${i + 1} | ${f.type} | ${f.file} | ${f.severity} | ${f.message} |`);
    });
    lines.push("");
  }

  // Convention deviations
  if (groups.convention.length > 0) {
    lines.push("## Convention Deviations");
    lines.push("");
    lines.push("| # | Type | File | Line | Severity | Convention | Actual | Decision |");
    lines.push("|---|------|------|------|----------|------------|--------|----------|");
    groups.convention.forEach((f, i) => {
      const decision = (f.severity === "medium" || f.severity === "high") ? "[DECIDE]" : "";
      const fileLine = f.line || "";
      lines.push(`| ${i + 1} | ${f.type} | ${f.file} | ${fileLine} | ${f.severity} | ${f.convention || ""} | ${f.actual || ""} | ${decision} |`);
    });
    lines.push("");
  }

  // Dependency changes
  if (groups.dependency.length > 0) {
    lines.push("## Dependency Changes");
    lines.push("");
    lines.push("| # | Type | Package | Old Version | New Version | Severity |");
    lines.push("|---|------|---------|-------------|-------------|----------|");
    groups.dependency.forEach((f, i) => {
      lines.push(`| ${i + 1} | ${f.type} | ${f.package} | ${f.old_version || "—"} | ${f.new_version || "—"} | ${f.severity} |`);
    });
    lines.push("");
  }

  // Interface changes
  if (groups.interface.length > 0) {
    lines.push("## Interface Changes");
    lines.push("");
    lines.push("| # | Type | Package | Symbol | Severity | Description |");
    lines.push("|---|------|---------|--------|----------|-------------|");
    groups.interface.forEach((f, i) => {
      lines.push(`| ${i + 1} | ${f.type} | ${f.package} | ${f.symbol} | ${f.severity} | ${f.message} |`);
    });
    lines.push("");
  }

  // Recommendations for charter
  lines.push("## Recommendations for Charter");
  lines.push("");

  // Structural recommendations
  for (const f of groups.structural) {
    if (f.type === "package_added") {
      lines.push(`- [ ] Update structural map: new package \`${f.package}\``);
    } else if (f.type === "package_removed") {
      lines.push(`- [ ] Update structural map: remove package \`${f.package}\``);
    }
  }

  // Convention recommendations (only DECIDE items)
  const decideItems = groups.convention.filter(f => f.severity === "medium" || f.severity === "high");
  for (const f of decideItems) {
    lines.push(`- [ ] [DECIDE] ${f.type}: \`${f.convention}\` → \`${f.actual}\` (${f.file})`);
  }

  // Dependency recommendations
  for (const f of groups.dependency) {
    if (f.type === "dep_added") {
      lines.push(`- [ ] Update dependency list: +${f.package} ${f.new_version}`);
    } else if (f.type === "dep_removed") {
      lines.push(`- [ ] Update dependency list: -${f.package}`);
    } else {
      lines.push(`- [ ] Note version change: ${f.package} ${f.old_version} → ${f.new_version}`);
    }
  }

  // Interface recommendations
  for (const f of groups.interface) {
    if (f.type === "export_added") {
      lines.push(`- [ ] Update interface map: +${f.symbol} in ${f.package}`);
    } else if (f.type === "export_removed") {
      lines.push(`- [ ] Update interface map: -${f.symbol} in ${f.package}`);
    } else if (f.type === "signature_changed") {
      lines.push(`- [ ] Update interface map: ${f.symbol} signature changed in ${f.package}`);
    }
  }

  if (lines[lines.length - 1] === "") {
    // No recommendations
    lines.push("No actionable recommendations.");
  }

  lines.push("");
  return lines.join("\n");
}

// ── Main ──

function run() {
  const findings = readFindings();

  if (findings.length === 0) {
    process.stdout.write("No drift detected.\n");
    process.exit(0);
  }

  const report = generateReport(findings);
  process.stdout.write(report);
  process.exit(1);
}

run();
