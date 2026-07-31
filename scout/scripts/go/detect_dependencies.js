#!/usr/bin/env node
// detect_dependencies.js — detect dependency changes between two commits via go.mod diff
// Use: node detect_dependencies.js <old-hash> <new-hash>
"use strict";

const { execSync } = require("child_process");

const oldHash = process.argv[2];
const newHash = process.argv[3];

if (!oldHash || !newHash) {
  process.stderr.write("Usage: node detect_dependencies.js <old-hash> <new-hash>\n");
  process.exit(1);
}

/**
 * Parse a go.mod require block from git show output.
 * Returns a map of package → version.
 */
function parseGoMod(content) {
  const deps = {};
  if (!content) return deps;

  const lines = content.split("\n");
  let inRequire = false;

  for (const line of lines) {
    const trimmed = line.trim();

    if (trimmed === "require (") {
      inRequire = true;
      continue;
    }
    if (trimmed === ")") {
      inRequire = false;
      continue;
    }

    // Single-line require
    const singleMatch = trimmed.match(/^require\s+(\S+)\s+(\S+)/);
    if (singleMatch) {
      deps[singleMatch[1]] = singleMatch[2];
      continue;
    }

    // Inside require block
    if (inRequire) {
      // Skip comments and indirect markers
      const depMatch = trimmed.match(/^(\S+)\s+(\S+)/);
      if (depMatch) {
        deps[depMatch[1]] = depMatch[2];
      }
    }
  }

  return deps;
}

/**
 * Get go.mod content at a specific commit.
 */
function getGoModAt(hash) {
  try {
    return execSync(`git show ${hash}:go.mod`, { encoding: "utf8" });
  } catch {
    return "";
  }
}

/**
 * Compare two semver-ish strings and determine the bump type.
 * Returns "major", "minor", "patch", or "other".
 */
function versionBumpType(oldVer, newVer) {
  // Strip leading v
  const o = oldVer.replace(/^v/, "").split(".");
  const n = newVer.replace(/^v/, "").split(".");

  if (o.length < 3 || n.length < 3) return "other";

  const oMajor = parseInt(o[0], 10);
  const nMajor = parseInt(n[0], 10);
  if (nMajor !== oMajor) return "major";

  const oMinor = parseInt(o[1], 10);
  const nMinor = parseInt(n[1], 10);
  if (nMinor !== oMinor) return "minor";

  return "patch";
}

function run() {
  const oldMod = parseGoMod(getGoModAt(oldHash));
  const newMod = parseGoMod(getGoModAt(newHash));

  const oldPkgs = new Set(Object.keys(oldMod));
  const newPkgs = new Set(Object.keys(newMod));
  let hasFindings = false;

  // New dependencies
  for (const pkg of newPkgs) {
    if (!oldPkgs.has(pkg)) {
      hasFindings = true;
      process.stdout.write(JSON.stringify({
        category: "dependency",
        type: "dep_added",
        severity: "medium",
        package: pkg,
        old_version: "",
        new_version: newMod[pkg],
        message: `New dependency: ${pkg} ${newMod[pkg]}`
      }) + "\n");
    }
  }

  // Removed dependencies
  for (const pkg of oldPkgs) {
    if (!newPkgs.has(pkg)) {
      hasFindings = true;
      process.stdout.write(JSON.stringify({
        category: "dependency",
        type: "dep_removed",
        severity: "high",
        package: pkg,
        old_version: oldMod[pkg],
        new_version: "",
        message: `Dependency removed: ${pkg} ${oldMod[pkg]}`
      }) + "\n");
    }
  }

  // Version changes
  for (const pkg of newPkgs) {
    if (oldPkgs.has(pkg) && oldMod[pkg] !== newMod[pkg]) {
      const bumpType = versionBumpType(oldMod[pkg], newMod[pkg]);
      let severity = "low";
      let type = "dep_patch_bump";

      if (bumpType === "major") {
        severity = "high";
        type = "dep_major_bump";
      } else if (bumpType === "minor") {
        severity = "medium";
        type = "dep_minor_bump";
      }

      hasFindings = true;
      process.stdout.write(JSON.stringify({
        category: "dependency",
        type: type,
        severity: severity,
        package: pkg,
        old_version: oldMod[pkg],
        new_version: newMod[pkg],
        message: `${bumpType} version bump: ${pkg} ${oldMod[pkg]} → ${newMod[pkg]}`
      }) + "\n");
    }
  }

  process.exit(hasFindings ? 1 : 0);
}

run();
