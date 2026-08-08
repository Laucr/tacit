# runner.go skeleton

The online path: iterate accepted rows, call the adapter's `Run`,
route the outcome to results / skipped / failures. **Standard library
only.**

Copy this file verbatim. The user does not edit it.

## Skeleton

```go
package main

import (
	"context"
	"fmt"
	"os"
)

// runOnline decodes input, calls Run per accepted row, and writes the
// four output files. Setup must have been called by main before this.
func runOnline(ctx context.Context, inputPath, outDir string, limit int) error {
	out := outputPaths(outDir, inputPath)

	parsedF, err := os.Create(out.parsed)
	if err != nil {
		return fmt.Errorf("create parsed.jsonl: %w", err)
	}
	defer parsedF.Close()
	resultsF, err := os.Create(out.results)
	if err != nil {
		return fmt.Errorf("create results.jsonl: %w", err)
	}
	defer resultsF.Close()
	skippedF, err := os.Create(out.skipped)
	if err != nil {
		return fmt.Errorf("create skipped.jsonl: %w", err)
	}
	defer skippedF.Close()
	failuresF, err := os.Create(out.failures)
	if err != nil {
		return fmt.Errorf("create failures.jsonl: %w", err)
	}
	defer failuresF.Close()

	var nOK, nSkipDecode, nSkipRun, nFailDecode, nFailRun int
	var acceptedTotal int

	scanErr := eachLine(inputPath, limit, func(r parseResult) bool {
		switch {
		case r.Failure != nil:
			nFailDecode++
			_ = writeJSONL(failuresF, r.Failure)
			logLine(r.Failure.Line, r.Failure.Mode, "FAIL", "decode: "+r.Failure.Error)
			return true

		case r.Skipped != nil:
			nSkipDecode++
			_ = writeJSONL(skippedF, r.Skipped)
			logLine(r.Skipped.Line, r.Skipped.Mode, "SKIP", "decode: "+r.Skipped.SkipReason)
			return true

		case r.Row != nil:
			acceptedTotal++
			_ = writeJSONL(parsedF, parsedRow{
				Line:  r.Row.lineNum,
				Mode:  r.Row.mode,
				Input: r.Row.input,
			})

			output, runErr := Run(ctx, r.Row.input)

			switch {
			case runErr != nil:
				if skip := asSkip(runErr); skip != nil {
					nSkipRun++
					_ = writeJSONL(skippedF, skippedRow{
						Line:       r.Row.lineNum,
						Mode:       r.Row.mode,
						Input:      r.Row.input,
						SkipStage:  "run",
						SkipReason: skip.Reason,
					})
					logLine(r.Row.lineNum, r.Row.mode, "SKIP", "run: "+skip.Reason)
					return true
				}
				nFailRun++
				_ = writeJSONL(failuresF, failureRow{
					Line:       r.Row.lineNum,
					Mode:       r.Row.mode,
					Input:      r.Row.input,
					ErrorStage: "run",
					Error:      runErr.Error(),
				})
				logLine(r.Row.lineNum, r.Row.mode, "FAIL", "run: "+runErr.Error())

			default:
				nOK++
				_ = writeJSONL(resultsF, resultRow{
					Line:   r.Row.lineNum,
					Mode:   r.Row.mode,
					Input:  r.Row.input,
					Output: output,
				})
				logLine(r.Row.lineNum, r.Row.mode, "OK", "")
			}
			return true
		}
		return true
	})
	if scanErr != nil {
		return scanErr
	}

	fmt.Fprintf(os.Stdout,
		"[%s] accepted=%d success=%d skipped(decode+run)=%d+%d failed(decode+run)=%d+%d\n"+
			"  parsed=%s\n  results=%s\n  skipped=%s\n  failures=%s\n",
		binaryName,
		acceptedTotal, nOK,
		nSkipDecode, nSkipRun,
		nFailDecode, nFailRun,
		out.parsed, out.results, out.skipped, out.failures)

	if acceptedTotal == 0 {
		return fmt.Errorf("no accepted rows in %s", inputPath)
	}
	return nil
}

// logLine is the one-per-row stdout signal. Keep it tiny and stable —
// operators pipe this into grep/awk. Format:
//   line=<N> mode=<object|array> status=<OK|SKIP|FAIL> [detail]
func logLine(line int, mode, status, detail string) {
	if detail == "" {
		fmt.Fprintf(os.Stdout, "line=%d mode=%s status=%s\n", line, mode, status)
		return
	}
	fmt.Fprintf(os.Stdout, "line=%d mode=%s status=%s detail=%q\n", line, mode, status, detail)
}
```

## Why five outcomes are surfaced separately

The runner distinguishes:

- `decode-fail`   — the adapter's `DecodeObject`/`DecodeArray` returned an error
- `decode-skip`   — the adapter's `DecodeObject`/`DecodeArray` returned `Skip(...)`
- `run-fail`      — `Run` returned a non-skip error
- `run-skip`      — `Run` returned an `*ErrSkip`
- `ok`            — `Run` returned `(output, nil)`

Two rows in `failures.jsonl` with different `error_stage` values tell
very different stories: a decode failure is almost always a bad input
or a stale schema, while a run failure is almost always a real
production concern. The summary line separates them so the operator
sees "10 accepted, 7 ok, 2 run-skipped, 1 run-failed" at a glance.

## Why no goroutines / worker pool

The runner is deliberately sequential. Rationale:

- Per-row observability is the point. Interleaved log lines from
  concurrent workers destroy that.
- Real-service smoke tests are usually rate-limited by the callee.
  Concurrency only helps if the callee has spare capacity — which is
  a bad assumption for the "just poke it a few times" use case.
- Any user who genuinely wants parallelism can wrap the binary in
  `xargs -P` or write a fanout adapter — cheaper than adding a
  worker pool the 95% case doesn't want.

## Why write output files even in dry-run

Two reasons:

1. Ergonomic parity: an operator running `-dry-run` gets exactly the
   same `parsed.jsonl` they would from the online run, so downstream
   tools work identically.
2. Failure surface: decode errors and decode-skips still land in
   their proper files, so dry-run is a real "does my input file
   parse?" check, not just a syntax test.
