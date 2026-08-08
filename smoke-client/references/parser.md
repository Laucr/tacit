# parser.go skeleton

Generic JSONL parsing infrastructure. **Standard library only** — this
file compiles without knowing anything about the project. It defines:

- The `Decision`, `Skip`, `ErrSkip` types the adapter uses to signal
  intent to the runner.
- The `parsedRow` / `resultRow` / `skippedRow` / `failureRow` envelope
  types the four output files use.
- The scanner (`parseInputFile`) that dispatches each line to the
  adapter's `DecodeObject` or `DecodeArray`.
- `outputPaths` and `writeJSONL` helpers.

Copy this file verbatim. The user does not edit it.

## Skeleton

```go
package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

// -----------------------------------------------------------------------------
// Adapter-facing types
// -----------------------------------------------------------------------------

// Decision is what an adapter's DecodeObject / DecodeArray returns
// alongside the input value. Zero-value means Proceed.
type Decision struct {
	skip   bool
	reason string
}

// Proceed tells the runner: this row decoded fine, call Run.
func Proceed() Decision { return Decision{} }

// Skip tells the runner: this row decoded fine, but do not call Run.
// The row lands in skipped.jsonl with `stage: "decode"` and the reason.
func Skip(reason string) Decision { return Decision{skip: true, reason: reason} }

// ErrSkip lets adapter.Run signal a late skip — the input was
// accepted but the entry function itself decided the row is
// not-applicable. Wrap or return &ErrSkip{Reason: "..."}.
type ErrSkip struct{ Reason string }

func (e *ErrSkip) Error() string { return "smoke: skip: " + e.Reason }

// asSkip returns the ErrSkip inside err (via errors.As) or nil.
func asSkip(err error) *ErrSkip {
	var s *ErrSkip
	if errors.As(err, &s) {
		return s
	}
	return nil
}

// -----------------------------------------------------------------------------
// Row and output envelopes
// -----------------------------------------------------------------------------

// row is the internal representation of one accepted JSONL line.
// Only the runner sees this; output files use the envelope types below.
type row struct {
	lineNum int
	mode    string // "object" or "array"
	input   any    // whatever adapter.Decode* returned
}

// parsedRow is written to *.parsed.jsonl for every accepted input row.
type parsedRow struct {
	Line  int    `json:"line"`
	Mode  string `json:"mode"`
	Input any    `json:"input"`
}

// resultRow is written to *.results.jsonl on adapter.Run success.
type resultRow struct {
	Line   int    `json:"line"`
	Mode   string `json:"mode"`
	Input  any    `json:"input"`
	Output any    `json:"output"`
}

// skippedRow is written to *.skipped.jsonl in two situations:
//   - The adapter's Decode* returned Skip(reason)     → stage="decode"
//   - The adapter's Run returned an *ErrSkip          → stage="run"
type skippedRow struct {
	Line       int    `json:"line"`
	Mode       string `json:"mode"`
	Input      any    `json:"input,omitempty"` // may be nil when Decode skipped early
	SkipStage  string `json:"skip_stage"`
	SkipReason string `json:"skip_reason"`
}

// failureRow is written to *.failures.jsonl in two situations:
//   - The adapter's Decode* returned an error         → stage="decode"
//   - The adapter's Run returned a non-skip error     → stage="run"
type failureRow struct {
	Line       int    `json:"line"`
	Mode       string `json:"mode"`
	Input      any    `json:"input,omitempty"` // may be nil when Decode errored
	ErrorStage string `json:"error_stage"`
	Error      string `json:"error"`
}

// -----------------------------------------------------------------------------
// Output paths
// -----------------------------------------------------------------------------

type outputSet struct {
	parsed, results, skipped, failures string
}

func outputPaths(outDir, inputPath string) outputSet {
	base := filepath.Base(inputPath)
	for _, ext := range []string{".jsonl", ".ndjson", ".json"} {
		if stripped, ok := strings.CutSuffix(base, ext); ok {
			base = stripped
			break
		}
	}
	join := func(suffix string) string { return filepath.Join(outDir, base+suffix) }
	return outputSet{
		parsed:   join(".parsed.jsonl"),
		results:  join(".results.jsonl"),
		skipped:  join(".skipped.jsonl"),
		failures: join(".failures.jsonl"),
	}
}

// -----------------------------------------------------------------------------
// JSONL scanner
// -----------------------------------------------------------------------------

// parseResult carries every kind of outcome the scanner can produce.
// The scanner does NOT hold everything in memory — it streams rows
// out one at a time via a callback. But for small inputs (the typical
// smoke case), callers collect the whole slice via collectAll.
type parseResult struct {
	Row     *row        // non-nil on Proceed
	Skipped *skippedRow // non-nil on Skip
	Failure *failureRow // non-nil on decode error
}

// eachLine streams parse outcomes to fn. Stops early when fn returns
// false. `limit` bounds the number of accepted rows (Row != nil);
// skipped/failed lines do not count toward the limit.
func eachLine(path string, limit int, fn func(parseResult) bool) error {
	f, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("open input: %w", err)
	}
	defer f.Close()

	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 1<<16), 16<<20) // up to 16 MB per line

	accepted := 0
	lineNum := 0
	for sc.Scan() {
		lineNum++
		raw := sc.Bytes()
		line := trimSpaceBytes(raw)
		if len(line) == 0 {
			continue
		}

		res := decodeOne(line, lineNum)
		if !fn(res) {
			return nil
		}
		if res.Row != nil {
			accepted++
			if limit > 0 && accepted >= limit {
				return nil
			}
		}
	}
	if err := sc.Err(); err != nil {
		return fmt.Errorf("scan input: %w", err)
	}
	return nil
}

// decodeOne dispatches one JSONL line to the adapter based on its
// leading byte.
func decodeOne(line []byte, lineNum int) parseResult {
	switch line[0] {
	case '{':
		in, dec, err := DecodeObject(line, lineNum)
		return classifyDecode(lineNum, "object", in, dec, err)
	case '[':
		if DecodeArray == nil {
			return parseResult{Failure: &failureRow{
				Line: lineNum, Mode: "array",
				ErrorStage: "decode",
				Error:      "adapter does not implement DecodeArray (Mode B disabled)",
			}}
		}
		in, dec, err := DecodeArray(line, lineNum)
		return classifyDecode(lineNum, "array", in, dec, err)
	default:
		return parseResult{Failure: &failureRow{
			Line: lineNum, Mode: "unknown",
			ErrorStage: "decode",
			Error: fmt.Sprintf("unrecognised JSONL shape (first char %q); "+
				"expected '{' or '['", string(line[0])),
		}}
	}
}

func classifyDecode(lineNum int, mode string, in any, dec Decision, err error) parseResult {
	if err != nil {
		return parseResult{Failure: &failureRow{
			Line: lineNum, Mode: mode,
			ErrorStage: "decode",
			Error:      err.Error(),
		}}
	}
	if dec.skip {
		return parseResult{Skipped: &skippedRow{
			Line: lineNum, Mode: mode,
			Input:      in, // may be nil, adapter's choice
			SkipStage:  "decode",
			SkipReason: dec.reason,
		}}
	}
	if in == nil {
		return parseResult{Failure: &failureRow{
			Line: lineNum, Mode: mode,
			ErrorStage: "decode",
			Error:      "adapter returned nil input without Skip or error",
		}}
	}
	return parseResult{Row: &row{lineNum: lineNum, mode: mode, input: in}}
}

func trimSpaceBytes(b []byte) []byte {
	i := 0
	for i < len(b) && (b[i] == ' ' || b[i] == '\t' || b[i] == '\r' || b[i] == '\n') {
		i++
	}
	j := len(b)
	for j > i && (b[j-1] == ' ' || b[j-1] == '\t' || b[j-1] == '\r' || b[j-1] == '\n') {
		j--
	}
	return b[i:j]
}

// -----------------------------------------------------------------------------
// runDry — the offline path
// -----------------------------------------------------------------------------

// runDry decodes input and writes only *.parsed.jsonl. Setup and Run
// are NOT called. Rows that Decode* skipped go to *.skipped.jsonl so
// the operator sees why; rows that failed to decode go to
// *.failures.jsonl.
func runDry(ctx context.Context, inputPath, outDir string, limit int) error {
	_ = ctx // reserved for future use (adapter dry hooks, cancellation)

	out := outputPaths(outDir, inputPath)
	parsedF, err := os.Create(out.parsed)
	if err != nil {
		return fmt.Errorf("create parsed.jsonl: %w", err)
	}
	defer parsedF.Close()
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

	var nOK, nSkip, nFail int
	scanErr := eachLine(inputPath, limit, func(r parseResult) bool {
		switch {
		case r.Row != nil:
			nOK++
			_ = writeJSONL(parsedF, parsedRow{Line: r.Row.lineNum, Mode: r.Row.mode, Input: r.Row.input})
		case r.Skipped != nil:
			nSkip++
			_ = writeJSONL(skippedF, r.Skipped)
		case r.Failure != nil:
			nFail++
			_ = writeJSONL(failuresF, r.Failure)
		}
		return true
	})
	if scanErr != nil {
		return scanErr
	}

	fmt.Fprintf(os.Stdout,
		"[%s dry] rows=%d skipped=%d failed=%d  (parsed=%s skipped=%s failures=%s)\n",
		binaryName, nOK, nSkip, nFail, out.parsed, out.skipped, out.failures)
	if nOK == 0 {
		return fmt.Errorf("no accepted rows in %s", inputPath)
	}
	return nil
}

// -----------------------------------------------------------------------------
// writeJSONL — small helper used by runDry and runOnline
// -----------------------------------------------------------------------------

func writeJSONL(w io.Writer, v any) error {
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	return enc.Encode(v)
}
```

Add `"context"` to the imports if your `go` version needs it explicit;
otherwise the reference to `ctx` in `runDry` is enough for the compiler
to pull it in. (In practice keep imports tidy — `goimports` will fix
this on save.)

## Why the scanner streams instead of buffering

The typical smoke input is small (5–500 rows). But the scanner is a
streaming design anyway so a curious operator can hand it a
10,000-line prod log without exploding memory. The buffer cap is
16 MB per line, which is generous for encoded event logs.

## Why Decision is a struct, not `(bool, string)`

Two reasons:

1. The zero value (`Decision{}`) means Proceed. Adapters that never
   skip can `return in, Decision{}, nil` without touching the flag.
2. Room to add future fields (a structured reason type, a
   per-skip metric bucket) without breaking the signature.

The trade-off is that a caller has to write `Skip("reason")` instead
of `true, "reason"` — a fair price for a stable contract.

## Why `DecodeArray` is a variable (not a required function)

Not every adapter wants to support Mode B. Declaring `DecodeArray` as
a `var` in `adapter.go` — of type `func([]byte, int) (any, Decision, error)`
— lets the user set it to `nil` to disable Mode B cleanly. The scanner
notices and writes a decode failure with a useful message rather than
segfaulting.
