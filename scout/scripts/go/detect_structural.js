#!/usr/bin/env node
// detect_structural.js — detect structural changes between two commits via git diff
// Use: node detect_structural.js <old-hash> <new-hash>
"use strict";

const { execSync } = require("child_process");
const path = require("path");

const oldHash = process.argv[2];
const newHash = process.argv[3];

if (!oldHash || !newHash) {
  process.stderr.write("Usage: node detect_structural.js <old-hash> <new-hash>\n");
  process.exit(1);
}

/**
 * Run git diff --name-status between two commits for Go files.
 * Returns lines like: "A\tpkg/new/file.go" or "R090\told.go\tnew.go"
 */
function gitDiffNameStatus(oldH, newH) {
  try {
    const out = execSync(
      `git diff --name-status ${oldH}..${newH} -- '*.go'`,
      { encoding: "utf8", maxBuffer: 10 * 1024 * 1024 }
    );
    return out.trim().split("\n").filter(Boolean);
  } catch (e) {
    process.stderr.write(`git diff failed: ${e.message}\n`);
    return [];
  }
}

/**
 * Extract the Go package directory from a file path.
 * e.g., "pkg/api/handler.go" → "pkg/api"
 */
function packageDir(filePath) {
  return path.dirname(filePath);
}

function run() {
  const lines = gitDiffNameStatus(oldHash, newHash);
  if (lines.length === 0) {
    process.exit(0);
  }

  // Track changes per package
  const packageChanges = {}; // packageDir → { added: [], deleted: [], modified: [], renamed: [] }
  const allPackages = new Set();

  for (const line of lines) {
    const parts = line.split("\t");
    const status = parts[0];

    if (status === "A") {
      // Added
      const file = parts[1];
      const pkg = packageDir(file);
      allPackages.add(pkg);
      if (!packageChanges[pkg]) packageChanges[pkg] = { added: [], deleted: [], modified: [], renamed: [] };
      packageChanges[pkg].added.push(file);
    } else if (status === "D") {
      // Deleted
      const file = parts[1];
      const pkg = packageDir(file);
      allPackages.add(pkg);
      if (!packageChanges[pkg]) packageChanges[pkg] = { added: [], deleted: [], modified: [], renamed: [] };
      packageChanges[pkg].deleted.push(file);
    } else if (status === "M") {
      // Modified
      const file = parts[1];
      const pkg = packageDir(file);
      allPackages.add(pkg);
      if (!packageChanges[pkg]) packageChanges[pkg] = { added: [], deleted: [], modified: [], renamed: [] };
      packageChanges[pkg].modified.push(file);
    } else if (status.startsWith("R")) {
      // Renamed (R + similarity score, e.g., R090)
      const oldFile = parts[1];
      const newFile = parts[2];
      const oldPkg = packageDir(oldFile);
      const newPkg = packageDir(newFile);
      allPackages.add(oldPkg);
      allPackages.add(newPkg);
      if (!packageChanges[oldPkg]) packageChanges[oldPkg] = { added: [], deleted: [], modified: [], renamed: [] };
      if (!packageChanges[newPkg]) packageChanges[newPkg] = { added: [], deleted: [], modified: [], renamed: [] };
      packageChanges[oldPkg].renamed.push({ from: oldFile, to: newFile });
      if (oldPkg !== newPkg) {
        packageChanges[newPkg].renamed.push({ from: oldFile, to: newFile });
      }
    }
  }

  // Determine which packages are entirely new or entirely removed
  // A package is "new" if all its Go files are additions (no modifications or renames from existing)
  // A package is "removed" if all its Go files are deletions
  let hasFindings = false;

  for (const pkg of allPackages) {
    const changes = packageChanges[pkg];
    if (!changes) continue;

    const totalAdded = changes.added.length;
    const totalDeleted = changes.deleted.length;
    const totalModified = changes.modified.length;
    const totalRenamed = changes.renamed.length;

    // Check if this is an entirely new package (only additions, no other changes)
    if (totalAdded > 0 && totalDeleted === 0 && totalModified === 0 && totalRenamed === 0) {
      // Check if this package existed in the old commit
      try {
        execSync(`git ls-tree ${oldHash} -- "${pkg}/"`, { encoding: "utf8" });
        // Package existed — these are just new files in existing package
        for (const file of changes.added) {
          hasFindings = true;
          process.stdout.write(JSON.stringify({
            category: "structural",
            type: "file_added",
            severity: "medium",
            file: file,
            package: pkg,
            message: `New file added to existing package: ${file}`
          }) + "\n");
        }
      } catch {
        // Package didn't exist — this is a new package
        hasFindings = true;
        process.stdout.write(JSON.stringify({
          category: "structural",
          type: "package_added",
          severity: "high",
          file: pkg,
          package: pkg,
          message: `New package added: ${pkg} (${totalAdded} files)`
        }) + "\n");
      }
      continue;
    }

    // Check if package is entirely removed (only deletions)
    if (totalDeleted > 0 && totalAdded === 0 && totalModified === 0 && totalRenamed === 0) {
      // Check if any Go files remain in this package at the new commit
      try {
        const remaining = execSync(
          `git ls-tree ${newHash} -- "${pkg}/" | grep "\\.go$"`,
          { encoding: "utf8" }
        );
        if (!remaining.trim()) throw new Error("empty");
        // Some files remain — just individual deletions
        for (const file of changes.deleted) {
          hasFindings = true;
          process.stdout.write(JSON.stringify({
            category: "structural",
            type: "file_deleted",
            severity: "medium",
            file: file,
            package: pkg,
            message: `File deleted from package: ${file}`
          }) + "\n");
        }
      } catch {
        // No Go files remain — package removed
        hasFindings = true;
        process.stdout.write(JSON.stringify({
          category: "structural",
          type: "package_removed",
          severity: "high",
          file: pkg,
          package: pkg,
          message: `Package removed: ${pkg} (${totalDeleted} files)`
        }) + "\n");
      }
      continue;
    }

    // Mixed changes — report individually
    for (const file of changes.added) {
      hasFindings = true;
      process.stdout.write(JSON.stringify({
        category: "structural",
        type: "file_added",
        severity: "medium",
        file: file,
        package: pkg,
        message: `New file: ${file}`
      }) + "\n");
    }

    for (const file of changes.deleted) {
      hasFindings = true;
      process.stdout.write(JSON.stringify({
        category: "structural",
        type: "file_deleted",
        severity: "medium",
        file: file,
        package: pkg,
        message: `File deleted: ${file}`
      }) + "\n");
    }

    for (const file of changes.modified) {
      hasFindings = true;
      process.stdout.write(JSON.stringify({
        category: "structural",
        type: "file_modified",
        severity: "low",
        file: file,
        package: pkg,
        message: `File modified: ${file}`
      }) + "\n");
    }

    for (const rename of changes.renamed) {
      hasFindings = true;
      process.stdout.write(JSON.stringify({
        category: "structural",
        type: "file_renamed",
        severity: "medium",
        file: rename.to,
        package: pkg,
        message: `File renamed: ${rename.from} → ${rename.to}`
      }) + "\n");
    }
  }

  process.exit(hasFindings ? 1 : 0);
}

run();
