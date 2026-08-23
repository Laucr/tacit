# Go Static Checks

Baseline checks for Go code quality. These apply to **all** Go code changes regardless of spec — they enforce language-specific standards. Universal (language-independent) checks live in [common_checks.md](./common_checks.md) and always run, including on non-Go projects.

Scripts are plain JavaScript (Node.js) — no compilation, no dependencies beyond what's already available in any Claude Code / codex environment.

Read this reference when the project being verified is a Go project.

## Checks

| Check | Script | What it catches |
|---|---|---|
| Logging | `scripts/go/check_logging.js` | `fmt.Println/Print/Printf` used instead of `log` package |
| Error handling | `scripts/go/check_errors.js` | Ignored errors (`_ =` pattern), unhandled error returns |
| Context propagation | `scripts/go/check_context.js` | Missing `ctx` parameter, `context.Background()` replacing an available `ctx`, `context.TODO()` in non-placeholder code |
| Deferred cleanup | `scripts/go/check_defer.js` | `context.WithCancel/Timeout/Deadline` without `defer cancel()`, opened resources without `defer Close()` |

## How to Run

Each check script is a standalone Node.js script. Run against one or more Go files:

```bash
node scripts/go/check_logging.js ./path/to/file.go ./path/to/other.go
node scripts/go/check_errors.js ./path/to/file.go
node scripts/go/check_context.js ./path/to/file.go
node scripts/go/check_defer.js ./path/to/file.go
```

Or run all checks against changed files:

```bash
for check in scripts/go/check_*.js; do
  node "$check" $(git diff --name-only --diff-filter=AM -- '*.go')
done
```

## Output Format

Each script outputs JSON lines (one per finding) to stdout:

```json
{"file": "cmd/server.go", "line": 42, "severity": "warning", "check": "logging", "message": "fmt.Println found — use log package instead", "code": "fmt.Println(\"hello\")"}
```

Exit code: `0` = no findings, `1` = findings present.

Severity levels:
- `error` — Must fix. Violates a hard rule (e.g., missing defer cancel).
- `warning` — Should fix. Likely a problem (e.g., fmt.Println, ignored error).
- `info` — Worth reviewing. Might be intentional (e.g., context.TODO in a test file).

## When to Skip

- **Test files (`*_test.go`)**: `fmt.Println` is acceptable in tests for debugging output. Logging checks run at `info` level instead of `warning`.
- **Generated files**: Skip files with `// Code generated` header.
- **Vendor directory**: Skip `vendor/`.

## Adding New Checks

To add a new Go check:

1. Create `scripts/go/check_<name>.js`
2. Follow the same CLI interface: accepts file paths as args, outputs JSON lines to stdout, exits 0/1
3. Add it to the table above
