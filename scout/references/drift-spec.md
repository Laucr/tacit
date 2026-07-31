# Drift Detection Specification

Reference document for scout's detection scripts. Explains each drift category, the detection method, output schema, and severity criteria.

Scripts are plain JavaScript (Node.js) — no external dependencies. They follow the same interface pattern as bailiff's check scripts: accept arguments, output JSON lines to stdout, exit 0 (no findings) or 1 (findings present).

---

## Scripts

| Script | Phase | What it detects |
|---|---|---|
| `scripts/go/detect_structural.js` | 1 | New/removed/renamed packages and files via git diff |
| `scripts/go/detect_conventions.js` | 2 | Convention deviations in changed Go files against rules spec |
| `scripts/go/detect_dependencies.js` | 3 | Dependency additions, removals, and version changes in go.mod |
| `scripts/go/detect_interfaces.js` | 4 | Exported symbol changes (functions, types, interfaces) |
| `scripts/go/severity_filter.js` | 5 | Combines all findings, assigns severity, generates report |

---

## Output Schema

All detection scripts output JSON lines (one per finding) to stdout. Each line has a common envelope:

```json
{
  "category": "structural|convention|dependency|interface",
  "type": "<specific change type>",
  "severity": "low|medium|high",
  "file": "<file path>",
  "message": "<human-readable description>",
  ...category-specific fields
}
```

### Structural Findings

```json
{
  "category": "structural",
  "type": "package_added|package_removed|file_added|file_deleted|file_renamed|file_modified",
  "severity": "low|medium|high",
  "file": "pkg/newfeature/handler.go",
  "package": "pkg/newfeature",
  "message": "New package added: pkg/newfeature (3 files)"
}
```

Severity:
- **low** — file modified within existing package
- **medium** — files added/removed within existing package
- **high** — entire package added/removed/renamed

### Convention Findings

```json
{
  "category": "convention",
  "type": "error_handling|logging|context|defer|naming|type_definition",
  "severity": "low|medium|high",
  "file": "pkg/api/handler.go",
  "line": 42,
  "convention": "errors.Wrap(err, \"context\")",
  "actual": "fmt.Errorf(\"context: %w\", err)",
  "message": "Error wrapping pattern differs from convention",
  "files_affected": 4
}
```

Severity:
- **low** — single occurrence, minor style difference
- **medium** — pattern appears in multiple files, could indicate intentional shift
- **high** — directly contradicts a fundamental convention rule

### Dependency Findings

```json
{
  "category": "dependency",
  "type": "dep_added|dep_removed|dep_major_bump|dep_minor_bump|dep_patch_bump",
  "severity": "low|medium|high",
  "package": "github.com/pkg/errors",
  "old_version": "v0.9.1",
  "new_version": "",
  "message": "Dependency removed: github.com/pkg/errors v0.9.1"
}
```

Severity:
- **low** — patch version bump
- **medium** — minor version bump, or new dependency added
- **high** — major version bump, or dependency removed

### Interface Findings

```json
{
  "category": "interface",
  "type": "export_added|export_removed|signature_changed|interface_modified",
  "severity": "low|medium|high",
  "file": "pkg/core/handler.go",
  "package": "pkg/core",
  "symbol": "NewHandler",
  "old_signature": "",
  "new_signature": "func NewHandler(ctx context.Context) *Handler",
  "message": "New exported function: NewHandler"
}
```

Severity:
- **low** — new export added (additive, non-breaking)
- **medium** — export signature changed (potentially breaking)
- **high** — export removed (breaking change)

---

## Severity Filter

`severity_filter.js` reads JSON lines from stdin, combines them, and produces:

1. **Overall severity** based on the highest individual severity and volume:
   - **minor** — only low-severity findings, or fewer than 5 total findings
   - **moderate** — any medium-severity findings, or more than 10 low-severity
   - **significant** — any high-severity findings, or more than 5 medium-severity

2. **Decision tags** for medium and high convention findings:
   - `[DECIDE]` — requires user input (update convention or flag as smell)
   - These become `[UPDATE]` or `[SMELL]` after user review

3. **Markdown report** written to stdout with sections:
   - Summary table
   - Structural changes
   - Convention deviations (with `[DECIDE]` tags)
   - Dependency changes
   - Interface changes
   - Recommendations for charter

---

## How to Run

### Individual scripts

```bash
# Phase 1: Structural
node scripts/go/detect_structural.js <old-hash> <new-hash>

# Phase 2: Conventions (pass rules file + changed Go files)
node scripts/go/detect_conventions.js <rules.mdc> file1.go file2.go ...

# Phase 3: Dependencies
node scripts/go/detect_dependencies.js <old-hash> <new-hash>

# Phase 4: Interfaces (pass old hash, new hash, and changed files)
node scripts/go/detect_interfaces.js <old-hash> <new-hash> file1.go file2.go ...

# Phase 5: Severity filter (pipe combined JSON)
cat phase1.json phase2.json phase3.json phase4.json | node scripts/go/severity_filter.js
```

### Exit codes

- `0` — no findings
- `1` — findings present

---

## Report Template

The severity filter generates a report following this structure:

```markdown
# Scout Drift Report

**Branch:** main
**Commit:** a3f2c1d
**Previous:** b2e4f6a
**Date:** 2026-04-03T14:30
**Overall severity:** moderate

## Summary

| Category | Low | Medium | High | Total |
|----------|-----|--------|------|-------|
| Structural | 2 | 1 | 0 | 3 |
| Convention | 3 | 2 | 0 | 5 |
| Dependency | 1 | 1 | 0 | 2 |
| Interface | 4 | 0 | 0 | 4 |
| **Total** | **10** | **4** | **0** | **14** |

## Structural Changes

| # | Type | Path | Severity | Description |
|---|------|------|----------|-------------|
| 1 | package_added | pkg/newfeature | high | New package with 3 files |

## Convention Deviations

| # | Type | File | Line | Severity | Convention | Actual | Decision |
|---|------|------|------|----------|------------|--------|----------|
| 1 | error_handling | pkg/api/handler.go | 42 | medium | errors.Wrap | fmt.Errorf | [DECIDE] |

## Dependency Changes

| # | Type | Package | Old Version | New Version | Severity |
|---|------|---------|-------------|-------------|----------|
| 1 | dep_added | github.com/newlib/v2 | — | v2.1.0 | medium |

## Interface Changes

| # | Type | Package | Symbol | Severity | Description |
|---|------|---------|--------|----------|-------------|
| 1 | export_added | pkg/core | NewHandler | low | New exported function |

## Recommendations for Charter

- [ ] Update structural map: new package `pkg/newfeature`
- [ ] [DECIDE] Error handling convention: `errors.Wrap` → `fmt.Errorf` (4 files)
- [ ] Update dependency list: +github.com/newlib/v2
- [ ] Update interface map: +NewHandler in pkg/core
```
