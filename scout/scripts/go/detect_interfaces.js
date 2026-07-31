#!/usr/bin/env node
// detect_interfaces.js — detect exported symbol changes between two commits
// Use: node detect_interfaces.js <old-hash> <new-hash> <file1.go> [file2.go ...]
"use strict";

const { execSync } = require("child_process");
const path = require("path");

const oldHash = process.argv[2];
const newHash = process.argv[3];
const changedFiles = process.argv.slice(4);

if (!oldHash || !newHash || changedFiles.length === 0) {
  process.stderr.write("Usage: node detect_interfaces.js <old-hash> <new-hash> <file1.go> [file2.go ...]\n");
  process.exit(1);
}

/**
 * Extract exported symbols from Go source content.
 * Returns an array of { name, kind, signature } objects.
 *
 * Exported = starts with uppercase letter.
 * Kinds: "func", "type", "const", "var", "method", "interface"
 */
function extractExports(content) {
  if (!content) return [];

  const lines = content.split("\n");
  const exports = [];
  let inBlockComment = false;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();

    // Track block comments
    if (trimmed.includes("/*")) inBlockComment = true;
    if (trimmed.includes("*/")) { inBlockComment = false; continue; }
    if (inBlockComment || trimmed.startsWith("//")) continue;

    // Exported function: func FuncName(...)
    const funcMatch = trimmed.match(/^func\s+([A-Z]\w*)\s*\((.*?)\)/);
    if (funcMatch) {
      // Get full signature up to the opening brace or end of line
      const sigLine = trimmed.replace(/\s*\{.*$/, "");
      exports.push({
        name: funcMatch[1],
        kind: "func",
        signature: sigLine
      });
      continue;
    }

    // Exported method: func (r *Type) MethodName(...)
    const methodMatch = trimmed.match(/^func\s+\(\w+\s+\*?(\w+)\)\s+([A-Z]\w*)\s*\((.*?)\)/);
    if (methodMatch) {
      const sigLine = trimmed.replace(/\s*\{.*$/, "");
      exports.push({
        name: `${methodMatch[1]}.${methodMatch[2]}`,
        kind: "method",
        signature: sigLine
      });
      continue;
    }

    // Exported type: type TypeName struct/interface/...
    const typeMatch = trimmed.match(/^type\s+([A-Z]\w*)\s+(\w+)/);
    if (typeMatch) {
      const kind = typeMatch[2] === "interface" ? "interface" : "type";
      exports.push({
        name: typeMatch[1],
        kind: kind,
        signature: trimmed.replace(/\s*\{.*$/, "")
      });
      continue;
    }

    // Exported const: const ConstName = ...
    const constMatch = trimmed.match(/^(?:const|var)\s+([A-Z]\w*)\s/);
    if (constMatch) {
      exports.push({
        name: constMatch[1],
        kind: trimmed.startsWith("const") ? "const" : "var",
        signature: trimmed
      });
    }
  }

  return exports;
}

/**
 * Get file content at a specific commit.
 */
function getFileAt(hash, filePath) {
  try {
    return execSync(`git show ${hash}:${filePath}`, { encoding: "utf8" });
  } catch {
    return "";
  }
}

function run() {
  let hasFindings = false;

  for (const filePath of changedFiles) {
    // Skip test files — their exports are not part of the public interface
    if (filePath.endsWith("_test.go")) continue;

    const pkg = path.dirname(filePath);
    const oldContent = getFileAt(oldHash, filePath);
    const newContent = getFileAt(newHash, filePath);

    const oldExports = extractExports(oldContent);
    const newExports = extractExports(newContent);

    const oldMap = {};
    for (const e of oldExports) oldMap[e.name] = e;

    const newMap = {};
    for (const e of newExports) newMap[e.name] = e;

    // New exports
    for (const name of Object.keys(newMap)) {
      if (!oldMap[name]) {
        hasFindings = true;
        process.stdout.write(JSON.stringify({
          category: "interface",
          type: "export_added",
          severity: "low",
          file: filePath,
          package: pkg,
          symbol: name,
          old_signature: "",
          new_signature: newMap[name].signature,
          message: `New exported ${newMap[name].kind}: ${name}`
        }) + "\n");
      }
    }

    // Removed exports
    for (const name of Object.keys(oldMap)) {
      if (!newMap[name]) {
        hasFindings = true;
        process.stdout.write(JSON.stringify({
          category: "interface",
          type: "export_removed",
          severity: "high",
          file: filePath,
          package: pkg,
          symbol: name,
          old_signature: oldMap[name].signature,
          new_signature: "",
          message: `Exported ${oldMap[name].kind} removed: ${name}`
        }) + "\n");
      }
    }

    // Signature changes
    for (const name of Object.keys(newMap)) {
      if (oldMap[name] && oldMap[name].signature !== newMap[name].signature) {
        hasFindings = true;
        process.stdout.write(JSON.stringify({
          category: "interface",
          type: "signature_changed",
          severity: "medium",
          file: filePath,
          package: pkg,
          symbol: name,
          old_signature: oldMap[name].signature,
          new_signature: newMap[name].signature,
          message: `Signature changed for ${name}`
        }) + "\n");
      }
    }
  }

  process.exit(hasFindings ? 1 : 0);
}

run();
