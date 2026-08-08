# main.go skeleton

The cmd entrypoint. Flag parsing, validation, dispatch. **Standard
library only** — anything project-specific lives in `adapter.go`.

Copy this file verbatim. The only intentional edits are:

- Optionally add project-specific flags (see "Adding flags" below).
- Optionally set `binaryName` to something more descriptive than
  `"smoke"`.

## Skeleton

```go
// Package main is a standalone smoke-test client. It reads a JSONL
// input file, feeds each row through the adapter defined in
// adapter.go, and writes parsed / results / skipped / failures JSONL
// artifacts.
//
// With -dry-run: only Decode* is called; nothing hits network.
// Without -dry-run: Setup runs once, then Run is called per row.
package main

import (
	"context"
	"flag"
	"fmt"
	"os"
	"path/filepath"
)

const binaryName = "smoke"

func main() {
	inputPath := flag.String("input", "",
		"Path to a JSONL input file. Each line is decoded as Mode A "+
			"(starts with '{') or Mode B (starts with '['). Required.")
	outDir := flag.String("output-dir", "",
		"Directory for *.parsed.jsonl / *.results.jsonl / *.skipped.jsonl "+
			"/ *.failures.jsonl. Default: dirname(-input).")
	cfgPath := flag.String("config", "",
		"Passed to adapter.Setup as-is. Ignored under -dry-run.")
	limit := flag.Int("limit", 0,
		"Max accepted rows to process. 0 = unlimited.")
	dryRun := flag.Bool("dry-run", false,
		"Decode input and write *.parsed.jsonl only. Adapter.Setup and "+
			"adapter.Run are NOT called. No network. No -config required.")

	// === Project-specific flags go here. See "Adding flags". ===

	flag.Usage = func() {
		fmt.Fprintf(os.Stderr,
			"usage: %s -input=<jsonl> [-output-dir=<dir>] "+
				"[-config=<path>] [-limit=N] [-dry-run]\n",
			binaryName)
		flag.PrintDefaults()
	}
	flag.Parse()

	if *inputPath == "" {
		flag.Usage()
		os.Exit(2)
	}
	if *outDir == "" {
		*outDir = filepath.Dir(*inputPath)
	}
	if err := os.MkdirAll(*outDir, 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "%s: mkdir output-dir: %v\n", binaryName, err)
		os.Exit(1)
	}

	ctx := context.Background()

	if *dryRun {
		if err := runDry(ctx, *inputPath, *outDir, *limit); err != nil {
			fmt.Fprintf(os.Stderr, "%s (dry): %v\n", binaryName, err)
			os.Exit(1)
		}
		return
	}

	if err := Setup(ctx, *cfgPath); err != nil {
		fmt.Fprintf(os.Stderr, "%s: setup: %v\n", binaryName, err)
		os.Exit(1)
	}
	if err := runOnline(ctx, *inputPath, *outDir, *limit); err != nil {
		fmt.Fprintf(os.Stderr, "%s: %v\n", binaryName, err)
		os.Exit(1)
	}
}
```

## Adding flags

For project-specific flags (a model override, a request tag, a
per-run trace-id prefix), add them next to the standard block and
expose their values to the adapter via a package-level variable:

```go
// main.go, next to the other flags:
model := flag.String("model", "", "Optional model override.")

// After flag.Parse():
adapterModelOverride = *model
```

Then declare the receiving variable in `adapter.go`:

```go
// adapter.go
var adapterModelOverride string

func Setup(ctx context.Context, cfgPath string) error {
    if adapterModelOverride != "" {
        // use it
    }
    ...
}
```

This keeps `main.go` free of project types and keeps `adapter.go` the
one place a reader looks for "what does this smoke actually do".

## Exit codes

- `0` — success
- `1` — runtime error (setup, decode mid-run, write mid-run)
- `2` — usage error (missing `-input`)

## What NOT to put in main.go

- Project imports. Anything under your module path lives in
  `adapter.go`.
- Framework blank imports (RPC plugins, tracing, metrics). If the
  adapter's `Setup` needs them, put them in `adapter.go` — that keeps
  `-dry-run` from dragging framework init into a laptop-only run.
- Business logic. `main` is 100 lines of flag plumbing; anything else
  is a smell.
