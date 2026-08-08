---
name: smoke-client
description: Scaffold a standalone JSONL-driven smoke-test client for a single function in an arbitrary Go project. Produces a `smoke/` directory with a small binary that reads a JSONL input file, runs each row through a user-supplied entry function, and writes parsed/results/skipped/failures JSONL artifacts. Use whenever the user wants to exercise one function end-to-end against real infrastructure without booting the surrounding service (HTTP server, message queue consumer, cron, etc.). Triggers on phrases like "smoke test client", "standalone harness for X", "JSONL-driven test for this function", "scaffold smoke/ for <feature>", "build a client that feeds N inputs through <function> and dumps outputs", "let me replay canned payloads through this handler". Don't undertrigger — if the user says "test <function> against staging" or "verify this call works on real data without running the whole service", reach for this skill.
---

# smoke-client

Scaffold a `smoke/` directory containing a standalone Go binary. The
binary reads a JSONL input file, runs each row through one user-chosen
entry function, and writes four output files:

- `<basename>.parsed.jsonl`   — one line per accepted input row, decoded
- `<basename>.results.jsonl`  — one line per success
- `<basename>.skipped.jsonl`  — one line per intentional skip
- `<basename>.failures.jsonl` — one line per error
`
Design goals, ranked:

1. **Framework-agnostic.** No hard-coded RPC stack, config loader, or
   plugin imports. Anything project-specific lives in the user-owned
   `adapter.go`.
2. **Small blast radius.** The user writes ~1 file (adapter.go). The
   other files compile as-is.
3. **Predictable JSONL shape.** Input decoding is user-controlled; the
   four output streams have a stable envelope so downstream tooling
   (diff, jq, load into a spreadsheet) works without per-project knowledge.
4. **Dry-run first.** `-dry-run` decodes input and writes
   `*.parsed.jsonl` without calling `Setup` or `Run` — nothing hits
   network, no config file required.

## When to use

Any of these should trigger the skill:

- "Build a smoke client for `<function>`"
- "Scaffold a JSONL harness that feeds inputs through `<function>` and dumps outputs"
- "I want to replay N canned records through `<handler>` without booting the service"
- "Standalone client to test `<function>` against staging"
- "Set up a small tool to hand-author test payloads and see what the model / service returns"
- "Hit `<endpoint>` on our staging server with a batch of canned requests and dump the responses"
- "Sanity-check the HTTP API from a JSONL of test requests"

The **entry under test** is usually one of:

- **An in-process Go function** — imported and called directly from
  `adapter.Run`. This is the default assumption of `references/adapter.md`.
- **A live HTTP endpoint** — reached over the wire from `adapter.Run`
  via `net/http`. Use the drop-in recipe in `references/http.md`.

Both use the same generic harness; only `adapter.go` differs.

Do **not** use this skill for:

- Regular unit tests (`go test`) — smoke is an operator's tool, not a CI gate.
- Load / benchmark work — smoke is sequential by design.
- Anything that needs to stand up a server socket — smoke is a client.

## Directory layout

The scaffold produces:

```
smoke/
  main.go              (generic — flag set + dispatch)
  parser.go            (generic — JSONL scanner, Mode A/B dispatch, envelope types)
  runner.go            (generic — iterate rows, call adapter, write outputs)
  adapter.go           (USER-OWNED — the 4-function contract, ~50–150 LOC)
  build.sh
  .gitignore
  README.md
  testdata/
    sample_input.jsonl
  bin/                 (gitignored; produced by build.sh)
```

The **only** file the user writes real logic in is `adapter.go`. The
other files are copied straight from the reference skeletons.

## The adapter contract

Everything project-specific goes through this interface. The generic
harness knows nothing about the user's types.

```go
// In adapter.go:

// Input is whatever the entry function needs. Define freely.
type Input struct { /* fields the runner will pass to Run */ }

// Decision controls what happens after a line decodes.
//   Proceed → runner calls Run; result goes to results/failures/skipped.
//   Skip    → runner writes to skipped.jsonl with the given reason.
// A returned error is fatal for the line (goes to failures).

// DecodeObject handles Mode A: a JSONL line that starts with '{'.
// Common case: an event log envelope where the payload of interest
// sits inside one field. Return (input, Proceed, nil) when the row is
// usable, (nil, Skip{reason}, nil) to silently ack, or (nil, _, err)
// on a hard decode failure.
func DecodeObject(line []byte, lineNum int) (*Input, Decision, error) { ... }

// DecodeArray handles Mode B: a JSONL line that starts with '['.
// Convenient for hand-authored payloads ("here's the message list I
// want to try"). Return nil to disable Mode B entirely.
func DecodeArray(line []byte, lineNum int) (*Input, Decision, error) { ... }

// Setup runs once, before any row is processed. Use it to load config,
// dial clients, initialise SDKs. `configPath` is whatever `-config`
// resolves to; ignore it if the entry doesn't need one. Not called in
// -dry-run mode.
func Setup(ctx context.Context, configPath string) error { ... }

// Run is the function under test — or a thin wrapper around it. The
// generic runner calls this once per accepted row. Return
// (output, nil) on success, (nil, ErrSkip{reason}) for a late skip
// (e.g., the input decoded fine but the entry itself has a "not for
// me" branch), or (nil, err) on failure.
func Run(ctx context.Context, in *Input) (any, error) { ... }
```

The user is free to add helpers in `adapter.go`; the generic code only
calls these four symbols.

## Output envelope

All four output files share this envelope, with one file-specific field:

| File              | Envelope                                         |
|-------------------|--------------------------------------------------|
| `parsed.jsonl`    | `{line, mode, input}`                            |
| `results.jsonl`   | `{line, mode, input, output}`                    |
| `skipped.jsonl`   | `{line, mode, input, skip_reason, skip_stage}`   |
| `failures.jsonl`  | `{line, mode, input, error, error_stage}`        |

- `line` — 1-based line number in the input file.
- `mode` — `"object"` or `"array"`.
- `input` — whatever the adapter returned from `DecodeObject`/`DecodeArray`.
- `output` — whatever the adapter's `Run` returned; encoded as-is.
- `skip_stage` — `"decode"` or `"run"`.
- `error_stage` — `"decode"` or `"run"`.

The envelope is fixed; the *shape inside `input`/`output`* is entirely
the user's call. That is the primary knob for "control the data
structure".

## Workflow

### Step 0: Pick the adapter recipe

Two off-the-shelf shapes cover most cases:

- **In-process function** — the entry is a Go function in the same
  module. `adapter.Run` imports and calls it directly. Use the
  generic template in `references/adapter.md`.
- **Live HTTP endpoint** — the entry is `POST /whatever` on a running
  server (staging, dev, localhost). `adapter.Run` sends an HTTP
  request via `net/http`. Use the drop-in in `references/http.md` —
  it comes with `-base-url`, `-method`, `-timeout`, `-header` flags
  and a per-row schema for method / path / query / body / headers.

If the target is neither (streaming RPC, WebSocket, signed handshake),
still start from `adapter.md` and write bespoke `Run` code.

### Step 1: Gather adapter-shaping facts

Ask (or extract from context) exactly the things needed to write
`adapter.go`. Batch with `AskUserQuestion` when helpful.

**For an in-process function target:**

1. **Entry function** — package + name + signature. Example:
   `pkg/foo.HandleRequest(ctx, *foo.Req) (*foo.Resp, error)`.
2. **Input shape** — what does one JSONL row look like? A log envelope
   with a nested payload (Mode A)? A raw list the user will hand-author
   (Mode B)? Both?
3. **Skip conditions** — under what conditions should a row be
   silently acked rather than errored? (e.g., "if `kind != 'target'`")
4. **Setup needs** — does the entry require a config file, env vars,
   dialled clients, an SDK init? If nothing → `Setup` is a no-op.
5. **Success shape** — what should land in `results.output`? The raw
   return value? A parsed slice of it? User's call.
6. **Late-skip sentinel** — does the entry itself have a
   "not-applicable" branch that returns a distinct error? If so,
   the adapter's `Run` should translate it to `ErrSkip`.

**For an HTTP-endpoint target:**

1. **Base URL** — where does the server live in the target env?
   (`https://api.staging.example.com`, `http://localhost:8080`, …)
2. **Endpoint(s)** — one path, or a fan-out across several? Method(s)?
3. **Auth** — bearer token, API key header, mTLS, session cookie?
4. **Request shape** — is the body one JSON object per row, or does
   the operator want to hand-author terse `[method, path, body]`
   arrays too?
5. **Success criteria** — which status codes count as success?
   Which count as intentional skips (e.g., `404` on a probe endpoint)?
6. **Response handling** — is the response JSON, or should we keep
   the raw body? Anything the operator wants to pull out into a top-
   level field?

### Step 2: Read the reference skeletons

Before writing anything, read:

- `references/main.md`     — main.go (flag set, dispatch)
- `references/parser.md`   — parser.go (JSONL scanner, envelope types)
- `references/runner.md`   — runner.go (loop, output routing)
- `references/adapter.md`  — adapter.go (the contract, worked examples)
- `references/http.md`     — HTTP-endpoint adapter recipe (only for HTTP targets)
- `references/build.md`    — build.sh, .gitignore, sample input, verify steps

### Step 3: Write the files

Order matters — `adapter.go` is the only interesting file:

1. `smoke/parser.go`  — copy from `references/parser.md` verbatim
2. `smoke/runner.go`  — copy from `references/runner.md` verbatim
3. `smoke/main.go`    — copy from `references/main.md`; the only edit
   is optionally adding domain-specific flags
4. `smoke/adapter.go` — write from scratch using
   `references/adapter.md` as the template (or copy `references/http.md`
   for an HTTP-endpoint target); this is where the consumer-specific
   facts land
5. `smoke/build.sh`, `.gitignore`, `README.md`, `testdata/sample_input.jsonl`

If `smoke/` already exists, ask whether to **replace** it, **coexist**
under a different name (e.g., `smoke_<slug>/`), or **abort**. Do not
overwrite silently.

### Step 4: Verify

```bash
go vet ./smoke/...
./smoke/build.sh
./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -dry-run
```

Expected:
- `go vet` is silent
- Binary builds to `smoke/bin/smoke`
- Dry run emits one `parsed.jsonl` and exits 0

If the build fails on missing native libs (`-lssl`, `-lcrypto`, …),
that is a CGO environment issue on the dev box, not a harness bug.
Report it verbatim and let the user resolve it.

Do **not** run the online path (no `-dry-run`) automatically — it may
hit paid APIs, staging quotas, or write real requests. Print the
command; let the user run it.

### Step 5: Hand off

Tell the user:

1. Binary path: `smoke/bin/smoke`
2. Dry command: `./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -dry-run`
3. Online command: `./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -config=smoke/config.<ext>`
4. Any env vars the user's `Setup` reads
5. Where outputs land (dirname of input, unless `-output-dir` was set)

## Flags (fixed, part of the contract)

```
-input       <path>   Required. JSONL input file.
-output-dir  <dir>    Where to write *.parsed / .results / .skipped / .failures.
                      Default: dirname(-input).
-config      <path>   Passed to adapter.Setup as-is. Ignored under -dry-run.
                      Default: empty string.
-limit       <int>    Max accepted rows to process. 0 = unlimited.
-dry-run              Decode only; do not call Setup or Run.
```

Adding project-specific flags is fine — put them in `main.go` and pass
them into the adapter via package-level vars or a `SetOptions(...)`
helper the user adds to `adapter.go`. Keep the five standard flags
intact.

## Design rules — non-negotiable

- **Single binary.** No build tags splitting "dry" from "online". The
  dispatch is a runtime `if *dryRun`.
- **No implicit framework imports.** The generic files import only the
  standard library. Any RPC / config / SDK import lives in `adapter.go`.
- **Envelope is stable.** Do not "improve" the output shape per project.
  Downstream tools depend on `line`, `mode`, `input`, `output`,
  `error`, `skip_reason` being where they are.
- **Sequential.** The runner processes one row at a time. Do not add
  concurrency; the smoke's value is per-row observability.
- **Silent about internals.** No progress bars, no ANSI colours. One
  line per row to stdout is enough: `line=N mode=X status=OK|SKIP|FAIL`.

## Reference files

- `references/main.md`    — main.go skeleton
- `references/parser.md`  — parser.go skeleton (JSONL scanner, Mode A/B, envelope)
- `references/runner.md`  — runner.go skeleton (loop, output routing)
- `references/adapter.md` — adapter.go template + worked examples (default: in-process function)
- `references/http.md`    — drop-in adapter.go for HTTP-endpoint targets
- `references/build.md`   — build.sh, .gitignore, testdata, verification
