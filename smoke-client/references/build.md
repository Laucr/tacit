# build.sh + .gitignore + testdata + verification

Supporting artifacts. Nearly invariant — copy and use as-is.

## build.sh

```bash
#!/usr/bin/env bash
# Build the smoke-test binary.
#
# Produces:
#   smoke/bin/smoke — reads JSONL input, feeds each row through the
#                     adapter, writes parsed/results/skipped/failures
#                     JSONL artifacts. -dry-run skips Setup + Run.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${REPO_ROOT}"
mkdir -p smoke/bin

echo "-> building smoke/bin/smoke"
go build -o smoke/bin/smoke ./smoke

echo
echo "built: ${REPO_ROOT}/smoke/bin/smoke"
echo
echo "usage:"
echo "  ./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -dry-run"
echo "  ./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl [-config=<path>]"
```

After writing, `chmod +x smoke/build.sh`.

### If the adapter imports transitive libs that need ldflags

Some ecosystems require build-time linker flags (proto registry
conflict policy, cgo library search paths, etc.). If — and only if —
the adapter's imports demand one, add it explicitly with a comment
explaining why. Do not add flags speculatively. Example (only if
needed):

```bash
go build \
  -ldflags="-X example.com/pkg.someVar=value" \
  -o smoke/bin/smoke \
  ./smoke
```

## .gitignore

```
bin/
logs/
log/
*.parsed.jsonl
*.results.jsonl
*.skipped.jsonl
*.failures.jsonl
```

The output-file patterns catch testdata-derived outputs the operator
runs locally — keep hand-authored test inputs under `testdata/` and
let generated outputs land alongside them, ignored.

## testdata/sample_input.jsonl

At least one Mode A row (JSON object) plus, if the adapter supports
Mode B, one Mode B row (JSON array). Both must be shaped to whatever
the adapter expects.

Template — replace with real values for the project's adapter:

```jsonl
{"kind":"target","order_id":"smoke-1","body":{"amount":42}}
{"kind":"other","order_id":"smoke-2","body":{"amount":7}}
[{"role":"user","content":"hand-authored payload for Mode B"}]
```

Keep the file tiny (3–20 rows). The smoke is for regression-shaped
probes and shape-checking — not bulk replay. Include at least:

1. One row that passes Decode and Run cleanly (verifies the happy path).
2. One row that Decode skips (verifies the skip branch is wired).
3. If Mode B is supported, one array-shape row.

## README.md

Adapt the following outline — nothing here is project-specific except
the parts you fill in:

```markdown
# smoke

Standalone JSONL-driven smoke client for `<function under test>`.
Reads a JSONL input file, runs each accepted row through the adapter
defined in `adapter.go`, writes four JSONL outputs.

## Build

    ./smoke/build.sh

Binary: `smoke/bin/smoke`.

## Flags

| Flag           | Default          | Purpose                                          |
|----------------|------------------|--------------------------------------------------|
| `-input`       | (required)       | JSONL input file                                 |
| `-output-dir`  | dirname(-input)  | Output directory                                 |
| `-config`      | ""               | Passed to adapter.Setup (unused under -dry-run)  |
| `-limit`       | 0                | Max accepted rows (0 = unlimited)                |
| `-dry-run`     | false            | Decode only; do not call Setup or Run            |

## Input format

Each non-empty line is one of:

- Mode A — a JSON object (`{...}`). Decoded by `adapter.DecodeObject`.
- Mode B — a JSON array (`[...]`). Decoded by `adapter.DecodeArray`
  when the adapter supports it.

See `adapter.go` for the exact shapes this project accepts.

## Outputs

Given `-input=path/to/foo.jsonl`, produces (alongside the input, or
under `-output-dir`):

- `foo.parsed.jsonl`   — one per accepted row: `{line, mode, input}`
- `foo.results.jsonl`  — one per success:      `{line, mode, input, output}`
- `foo.skipped.jsonl`  — one per skip:         `{line, mode, input, skip_stage, skip_reason}`
- `foo.failures.jsonl` — one per error:        `{line, mode, input, error_stage, error}`

## Env vars

<list anything Setup reads>

## Quick commands

    # dry (offline, no network)
    ./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -dry-run

    # online
    ./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -config=smoke/config.yaml
```

## Verify (after scaffolding)

```bash
go vet ./smoke/...             # must be silent
./smoke/build.sh               # produces smoke/bin/smoke
```

Then dry-run:

```bash
./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -dry-run
```

Expected:
- One line per accepted row in `testdata/sample_input.parsed.jsonl`.
- One line per Decode skip in `testdata/sample_input.skipped.jsonl`.
- Zero lines in `testdata/sample_input.failures.jsonl` if the sample
  is well-formed.
- Stdout: `[smoke dry] rows=<N> skipped=<K> failed=0 (parsed=... skipped=... failures=...)`.
- Exit 0.

If dry-run errors with "no accepted rows", either the sample doesn't
match the adapter's Mode A gate, or `DecodeObject` isn't returning
`Proceed()` for any row. Recheck the sample and the adapter side by
side.
