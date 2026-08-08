# adapter.go — the user-owned contract

This is the **only file with project-specific code**. The generic
harness (main.go / parser.go / runner.go) calls four symbols defined
here:

- `DecodeObject(line, lineNum) (any, Decision, error)` — function
- `DecodeArray`                                        — variable
- `Setup(ctx, configPath) error`                       — function
- `Run(ctx, input) (any, error)`                       — function

Everything else — the JSONL scanner, the output routing, the flag
set — comes for free.

> **HTTP-endpoint targets:** if the entry under test is a live HTTP
> server rather than an in-process Go function, use
> `references/http.md` instead — it's a complete drop-in `adapter.go`
> with per-row method/path/query/body/headers, matching flag additions
> for `main.go`, and status-code-based success/skip/fail classification.
> The rest of this file covers the in-process function case.

## Skeleton

Start from this template. It compiles as-is (both decoders reject
everything, `Setup` and `Run` are no-ops). Fill in the four sections
marked `// FILL IN`.

```go
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
)

// -----------------------------------------------------------------------------
// 1. Input / Output types  (FILL IN)
// -----------------------------------------------------------------------------

// Input is what the harness passes to Run. Define it however you
// want — a struct, a proto, a map. The generic runner never touches
// the fields; it just hands the value back to Run and also emits it
// verbatim into parsed / results / skipped / failures rows.
type Input struct {
	// e.g. RequestID string, Payload *foo.Req, Metadata map[string]string
}

// Output is what Run returns. Define it however you want; the runner
// json.Marshals it into results.jsonl. If your entry function already
// returns something JSON-serializable, you can skip defining an
// Output type and just return that value from Run.

// -----------------------------------------------------------------------------
// 2. Decoders  (FILL IN)
// -----------------------------------------------------------------------------

// DecodeObject parses a JSONL line that starts with '{'.
//
// Typical shape: your service reads events from a queue where each
// event is a JSON object with metadata + a nested payload. The Mode A
// decoder extracts the payload and shapes it into Input.
//
// Return one of:
//   (in, Proceed(),      nil)   — accepted; runner will call Run
//   (nil, Skip("reason"), nil)  — silent skip; lands in skipped.jsonl
//   (nil, Decision{},    err)   — decode failure; lands in failures.jsonl
func DecodeObject(line []byte, lineNum int) (*Input, Decision, error) {
	// Example: parse into a schema envelope, apply a filter gate,
	// pull the payload out.
	//
	//   var env struct {
	//       Kind    string          `json:"kind"`
	//       Payload json.RawMessage `json:"payload"`
	//   }
	//   if err := json.Unmarshal(line, &env); err != nil {
	//       return nil, Decision{}, fmt.Errorf("unmarshal envelope: %w", err)
	//   }
	//   if env.Kind != "target" {
	//       return nil, Skip("kind=" + env.Kind), nil
	//   }
	//   var in Input
	//   if err := json.Unmarshal(env.Payload, &in); err != nil {
	//       return nil, Decision{}, fmt.Errorf("unmarshal payload: %w", err)
	//   }
	//   return &in, Proceed(), nil

	return nil, Decision{}, errors.New("DecodeObject not implemented")
}

// DecodeArray parses a JSONL line that starts with '['. Convenient for
// hand-authored payloads:
//
//   [{"role":"user","content":"hi"},{"role":"user","content":"bye"}]
//
// Set to nil (see below) to disable Mode B entirely.
var DecodeArray = func(line []byte, lineNum int) (*Input, Decision, error) {
	// Example: treat the array as a message list and wrap it in Input.
	//
	//   var msgs []Message
	//   if err := json.Unmarshal(line, &msgs); err != nil {
	//       return nil, Decision{}, fmt.Errorf("unmarshal array: %w", err)
	//   }
	//   if len(msgs) == 0 {
	//       return nil, Decision{}, errors.New("empty array")
	//   }
	//   return &Input{Messages: msgs}, Proceed(), nil

	return nil, Decision{}, errors.New("DecodeArray not implemented")
}

// To disable Mode B, replace the assignment above with:
//   var DecodeArray func([]byte, int) (*Input, Decision, error) = nil
// and any input line starting with '[' will land in failures.jsonl
// with a clear "Mode B disabled" reason.

// -----------------------------------------------------------------------------
// 3. Setup  (FILL IN — or leave a no-op)
// -----------------------------------------------------------------------------

// Setup runs once, before the row loop starts, only in online mode
// (never in -dry-run).
//
// Use it for anything the entry function needs: reading a config
// file, dialling clients, loading env vars, initialising SDKs.
// configPath is whatever `-config` resolved to (may be "").
func Setup(ctx context.Context, configPath string) error {
	// Example:
	//   if configPath == "" {
	//       return errors.New("-config is required in online mode")
	//   }
	//   cfg, err := loadYAML(configPath)
	//   if err != nil { return err }
	//   client, err := myservice.Dial(cfg.Endpoint)
	//   if err != nil { return err }
	//   entryClient = client
	//   return nil

	return nil
}

// -----------------------------------------------------------------------------
// 4. Run  (FILL IN — the function under test, or a thin wrapper)
// -----------------------------------------------------------------------------

// Run is called once per accepted row. Return (output, nil) on
// success, (nil, &ErrSkip{Reason: "..."}) for a late skip, or
// (nil, err) on failure.
//
// The `in` argument is what DecodeObject/DecodeArray returned. If
// you're using a typed *Input, cast it back at the top:
//
//   input := in.(*Input)
func Run(ctx context.Context, in any) (any, error) {
	input := in.(*Input)
	_ = input

	// Example — call the real thing and translate its errors:
	//
	//   resp, err := myservice.HandleRequest(ctx, input.Payload)
	//   if errors.Is(err, myservice.ErrNotApplicable) {
	//       return nil, &ErrSkip{Reason: "not applicable"}
	//   }
	//   if err != nil {
	//       return nil, fmt.Errorf("HandleRequest: %w", err)
	//   }
	//   return resp, nil

	return nil, errors.New("Run not implemented")
}

// -----------------------------------------------------------------------------
// Optional helpers — put anything else the adapter needs here.
// -----------------------------------------------------------------------------

// Nothing here yet. Common additions:
//   - a filter helper reused by DecodeObject
//   - a response-parsing helper reused by Run
//   - package-level clients / config populated by Setup
//   - variables set from project-specific flags in main.go
```

## Worked examples

### Example 1: HTTP handler with a request envelope

The service consumes events, each event is a JSON object with a
`type` and a `body`. Only `type=purchase` should exercise the handler.

```go
type Input struct {
	OrderID string          `json:"order_id"`
	Body    json.RawMessage `json:"body"`
}

func DecodeObject(line []byte, lineNum int) (*Input, Decision, error) {
	var env struct {
		Type    string          `json:"type"`
		OrderID string          `json:"order_id"`
		Body    json.RawMessage `json:"body"`
	}
	if err := json.Unmarshal(line, &env); err != nil {
		return nil, Decision{}, fmt.Errorf("unmarshal event: %w", err)
	}
	if env.Type != "purchase" {
		return nil, Skip("type=" + env.Type), nil
	}
	if env.OrderID == "" {
		return nil, Decision{}, errors.New("order_id empty")
	}
	return &Input{OrderID: env.OrderID, Body: env.Body}, Proceed(), nil
}

// Mode B disabled for this consumer.
var DecodeArray func([]byte, int) (*Input, Decision, error)

var handler *purchase.Handler

func Setup(ctx context.Context, cfgPath string) error {
	cfg, err := config.Load(cfgPath)
	if err != nil {
		return err
	}
	handler = purchase.New(cfg)
	return nil
}

func Run(ctx context.Context, in any) (any, error) {
	input := in.(*Input)
	req := &purchase.Request{OrderID: input.OrderID, Body: input.Body}
	resp, err := handler.Handle(ctx, req)
	if err != nil {
		return nil, err
	}
	return resp, nil
}
```

### Example 2: LLM call, both input modes, structured output

A wrapper around an LLM completion. Mode A ingests production log
rows; Mode B accepts hand-authored message arrays for quick iteration.

```go
type Message struct {
	Role    string `json:"role"`
	Content string `json:"content"`
}

type Input struct {
	TraceID  string    `json:"trace_id,omitempty"`
	Messages []Message `json:"messages"`
}

type Output struct {
	Raw     string   `json:"raw"`
	Label   string   `json:"label,omitempty"`
	LabelOK bool     `json:"label_ok"`
}

func DecodeObject(line []byte, lineNum int) (*Input, Decision, error) {
	var env struct {
		TraceID  string `json:"trace_id"`
		Messages string `json:"messages"` // JSON-encoded array
		Skip     bool   `json:"skip"`
	}
	if err := json.Unmarshal(line, &env); err != nil {
		return nil, Decision{}, err
	}
	if env.Skip {
		return nil, Skip("skip=true"), nil
	}
	var msgs []Message
	if err := json.Unmarshal([]byte(env.Messages), &msgs); err != nil {
		return nil, Decision{}, fmt.Errorf("unmarshal messages: %w", err)
	}
	if len(msgs) == 0 {
		return nil, Decision{}, errors.New("no messages")
	}
	return &Input{TraceID: env.TraceID, Messages: msgs}, Proceed(), nil
}

var DecodeArray = func(line []byte, lineNum int) (*Input, Decision, error) {
	var msgs []Message
	if err := json.Unmarshal(line, &msgs); err != nil {
		return nil, Decision{}, err
	}
	if len(msgs) == 0 {
		return nil, Decision{}, errors.New("empty array")
	}
	return &Input{
		TraceID:  fmt.Sprintf("manual-line-%d", lineNum),
		Messages: msgs,
	}, Proceed(), nil
}

var llm *llmclient.Client

func Setup(ctx context.Context, cfgPath string) error {
	c, err := llmclient.New(cfgPath)
	if err != nil {
		return err
	}
	llm = c
	return nil
}

func Run(ctx context.Context, in any) (any, error) {
	input := in.(*Input)
	if last := input.Messages[len(input.Messages)-1]; last.Content == "" {
		return nil, &ErrSkip{Reason: "empty last-turn content"}
	}
	raw, err := llm.Complete(ctx, input.Messages)
	if err != nil {
		return nil, err
	}
	out := &Output{Raw: raw}
	var probe struct{ Label string `json:"label"` }
	if json.Unmarshal([]byte(raw), &probe) == nil && probe.Label != "" {
		out.Label = probe.Label
		out.LabelOK = true
	}
	return out, nil
}
```

## Guidelines

**Shape `Input` for legibility, not for the entry function.** The
runner emits `Input` into every output file's envelope, so an operator
diffing two runs sees exactly what changed. If your entry takes a
sprawling proto with 50 fields but the smoke only varies 3, define
`Input` to hold those 3 and construct the full proto inside `Run`.

**Prefer `Skip` over `error` when the input is *intentionally*
irrelevant.** `Skip` means "we saw this and chose not to act";
`error` means "something is wrong". Downstream tooling can filter
skipped.jsonl to a manageable size while treating failures.jsonl as
an alert queue.

**Late skips are for entries with an internal "not-applicable"
branch.** If your production handler quietly returns a sentinel error
for irrelevant rows, translate that sentinel into `&ErrSkip{...}` in
`Run` so the smoke's skipped-vs-failed accounting mirrors production.

**Keep helpers small.** `adapter.go` should be readable top-to-bottom.
If it grows past ~300 LOC, factor helpers into `adapter_helpers.go`
in the same directory — the generic harness doesn't care about file
count.

**Package-level state is fine.** `Setup` populating a package-level
client, and `Run` reading it, is the expected pattern. No dependency
injection required — this is a single-purpose binary.

## Things NOT to do in adapter.go

- Don't call `os.Exit` or `log.Fatal`. Return errors; let `main` exit.
- Don't spawn goroutines that outlive `Run` — the runner is
  sequential, background work will race the process exit.
- Don't reformat / re-encode `Input` inside `Run` just to log it. The
  runner already emits it into parsed.jsonl.
- Don't swallow real errors as `Skip`. If the entry failed for a real
  reason, that belongs in failures.jsonl.
