# HTTP-server adapter recipe

The generic harness knows nothing about HTTP — but "hit one endpoint
on a live server with N canned requests and dump the responses" is
the single most common smoke shape. This file is a drop-in
`adapter.go` for exactly that case: the entry under test is an HTTP
endpoint reached over the wire (staging, dev, localhost).

Use this when:

- The target is a **running HTTP server** you want to poke, not a Go
  function you can import. (For in-process `http.Handler` testing use
  the standard `adapter.md` template with `httptest.NewServer` inside
  `Setup`.)
- You want per-row control over method, path, query, headers, and
  body — driven from the JSONL input.
- You care about response status, headers, and body all landing in
  `results.jsonl` in a stable shape.

Skip this recipe when the endpoint needs a signed handshake,
streaming, or WebSocket — those don't fit a one-shot request/response
adapter cleanly. Fall back to `adapter.md` and write bespoke code.

## Flags added to main.go

Add these next to the standard flag block (see `main.md`, section
"Adding flags"):

```go
baseURL := flag.String("base-url", "",
    "HTTP base URL, e.g. https://api.staging.example.com. Required in "+
        "online mode. The per-row `path` is appended.")
defaultMethod := flag.String("method", "POST",
    "Default HTTP method when a row does not specify one.")
timeout := flag.Duration("timeout", 30*time.Second,
    "Per-request timeout.")
headerFlag := flag.String("header", "",
    "Comma-separated `K:V` default headers applied to every request. "+
        "Per-row headers override.")

// After flag.Parse():
adapterBaseURL       = *baseURL
adapterDefaultMethod = *defaultMethod
adapterTimeout       = *timeout
adapterDefaultHeaders = parseHeaderFlag(*headerFlag) // helper in adapter.go
```

Add `"time"` to `main.go`'s imports.

## adapter.go

```go
package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// -----------------------------------------------------------------------------
// Flag-fed globals (populated in main.go after flag.Parse)
// -----------------------------------------------------------------------------

var (
	adapterBaseURL        string
	adapterDefaultMethod  string
	adapterTimeout        time.Duration
	adapterDefaultHeaders map[string]string
)

// -----------------------------------------------------------------------------
// Input / Output
// -----------------------------------------------------------------------------

// Input is one HTTP request. Each field is optional except Path.
// Every field except Body can be defaulted from flags / prior rows.
type Input struct {
	Method  string            `json:"method,omitempty"`  // default: -method flag
	Path    string            `json:"path"`              // required; appended to -base-url
	Query   map[string]string `json:"query,omitempty"`   // encoded as ?k=v&...
	Headers map[string]string `json:"headers,omitempty"` // per-row headers; merged over -header defaults
	Body    json.RawMessage   `json:"body,omitempty"`    // raw JSON body; omit for GET-shaped requests

	// If non-empty, the runner accepts these status codes as SUCCESS.
	// Anything else routes to failures.jsonl. Default: [200, 201, 202, 204].
	AcceptStatuses []int `json:"accept_statuses,omitempty"`

	// If non-empty, the runner treats these status codes as intentional
	// SKIPs (skipped.jsonl with skip_stage="run"). Useful for endpoints
	// that return 404 or 409 on "not applicable" but reserve 5xx for
	// real failures.
	SkipStatuses []int `json:"skip_statuses,omitempty"`
}

// Output is what lands in results.jsonl / failures.jsonl / skipped.jsonl.
type Output struct {
	Status     int                 `json:"status"`
	StatusText string              `json:"status_text"`
	Headers    map[string][]string `json:"headers"`
	// Body is emitted as parsed JSON when Content-Type looks JSON-ish,
	// otherwise as a string. Keeps the results file diff-friendly.
	Body    any    `json:"body,omitempty"`
	BodyRaw string `json:"body_raw,omitempty"` // populated only when Body could not be JSON-decoded
	Elapsed string `json:"elapsed"`            // Go duration string, e.g. "142ms"
}

// -----------------------------------------------------------------------------
// Decoders
// -----------------------------------------------------------------------------

func DecodeObject(line []byte, lineNum int) (*Input, Decision, error) {
	var in Input
	if err := json.Unmarshal(line, &in); err != nil {
		return nil, Decision{}, fmt.Errorf("unmarshal request: %w", err)
	}
	if in.Path == "" {
		return nil, Decision{}, errors.New("path is required")
	}
	return &in, Proceed(), nil
}

// Mode B interprets the array as [method, path, body?, headers?] — a
// terse hand-authored shape. Comment out or set to nil to disable.
var DecodeArray = func(line []byte, lineNum int) (*Input, Decision, error) {
	var parts []json.RawMessage
	if err := json.Unmarshal(line, &parts); err != nil {
		return nil, Decision{}, err
	}
	if len(parts) < 2 {
		return nil, Decision{}, errors.New(
			"array form requires at least [method, path]")
	}
	in := &Input{}
	if err := json.Unmarshal(parts[0], &in.Method); err != nil {
		return nil, Decision{}, fmt.Errorf("part[0] method: %w", err)
	}
	if err := json.Unmarshal(parts[1], &in.Path); err != nil {
		return nil, Decision{}, fmt.Errorf("part[1] path: %w", err)
	}
	if len(parts) >= 3 && len(parts[2]) > 0 && string(parts[2]) != "null" {
		in.Body = parts[2]
	}
	if len(parts) >= 4 && len(parts[3]) > 0 && string(parts[3]) != "null" {
		if err := json.Unmarshal(parts[3], &in.Headers); err != nil {
			return nil, Decision{}, fmt.Errorf("part[3] headers: %w", err)
		}
	}
	return in, Proceed(), nil
}

// -----------------------------------------------------------------------------
// Setup
// -----------------------------------------------------------------------------

var httpClient *http.Client

func Setup(ctx context.Context, configPath string) error {
	if adapterBaseURL == "" {
		return errors.New("-base-url is required in online mode")
	}
	if _, err := url.Parse(adapterBaseURL); err != nil {
		return fmt.Errorf("bad -base-url: %w", err)
	}
	if adapterDefaultMethod == "" {
		adapterDefaultMethod = "POST"
	}
	if adapterTimeout <= 0 {
		adapterTimeout = 30 * time.Second
	}
	httpClient = &http.Client{Timeout: adapterTimeout}
	_ = configPath // unused; keep the signature stable
	return nil
}

// -----------------------------------------------------------------------------
// Run
// -----------------------------------------------------------------------------

var defaultAcceptStatuses = []int{200, 201, 202, 204}

func Run(ctx context.Context, in any) (any, error) {
	req, err := buildRequest(ctx, in.(*Input))
	if err != nil {
		return nil, err
	}

	start := time.Now()
	resp, err := httpClient.Do(req)
	elapsed := time.Since(start)
	if err != nil {
		return nil, fmt.Errorf("http.Do: %w", err)
	}
	defer resp.Body.Close()

	bodyBytes, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("read body: %w", err)
	}

	out := &Output{
		Status:     resp.StatusCode,
		StatusText: resp.Status,
		Headers:    resp.Header,
		Elapsed:    elapsed.String(),
	}

	if len(bodyBytes) > 0 {
		if looksJSON(resp.Header.Get("Content-Type"), bodyBytes) {
			var parsed any
			if json.Unmarshal(bodyBytes, &parsed) == nil {
				out.Body = parsed
			} else {
				out.BodyRaw = string(bodyBytes)
			}
		} else {
			out.BodyRaw = string(bodyBytes)
		}
	}

	input := in.(*Input)
	if containsInt(input.SkipStatuses, resp.StatusCode) {
		return nil, &ErrSkip{Reason: fmt.Sprintf(
			"status=%d (matches skip_statuses)", resp.StatusCode)}
	}

	accept := input.AcceptStatuses
	if len(accept) == 0 {
		accept = defaultAcceptStatuses
	}
	if !containsInt(accept, resp.StatusCode) {
		return out, fmt.Errorf("unexpected status %d %s (body=%s)",
			resp.StatusCode, resp.Status, truncate(bodyBytes, 400))
	}

	return out, nil
}

// -----------------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------------

func buildRequest(ctx context.Context, in *Input) (*http.Request, error) {
	method := in.Method
	if method == "" {
		method = adapterDefaultMethod
	}

	target, err := url.Parse(strings.TrimRight(adapterBaseURL, "/") + "/" + strings.TrimLeft(in.Path, "/"))
	if err != nil {
		return nil, fmt.Errorf("build url: %w", err)
	}
	if len(in.Query) > 0 {
		q := target.Query()
		for k, v := range in.Query {
			q.Set(k, v)
		}
		target.RawQuery = q.Encode()
	}

	var body io.Reader
	if len(in.Body) > 0 && string(in.Body) != "null" {
		body = bytes.NewReader(in.Body)
	}

	req, err := http.NewRequestWithContext(ctx, method, target.String(), body)
	if err != nil {
		return nil, err
	}

	// Default headers first, then per-row overrides.
	for k, v := range adapterDefaultHeaders {
		req.Header.Set(k, v)
	}
	for k, v := range in.Headers {
		req.Header.Set(k, v)
	}
	if body != nil && req.Header.Get("Content-Type") == "" {
		req.Header.Set("Content-Type", "application/json")
	}
	return req, nil
}

// parseHeaderFlag turns "K1:V1,K2:V2" into a map. Whitespace around
// keys and values is trimmed. Empty pairs are skipped.
func parseHeaderFlag(raw string) map[string]string {
	out := map[string]string{}
	for _, pair := range strings.Split(raw, ",") {
		pair = strings.TrimSpace(pair)
		if pair == "" {
			continue
		}
		k, v, ok := strings.Cut(pair, ":")
		if !ok {
			continue
		}
		out[strings.TrimSpace(k)] = strings.TrimSpace(v)
	}
	return out
}

func containsInt(xs []int, x int) bool {
	for _, v := range xs {
		if v == x {
			return true
		}
	}
	return false
}

func looksJSON(contentType string, body []byte) bool {
	if strings.Contains(contentType, "json") {
		return true
	}
	trimmed := bytes.TrimSpace(body)
	return len(trimmed) > 0 && (trimmed[0] == '{' || trimmed[0] == '[')
}

func truncate(b []byte, n int) string {
	if len(b) <= n {
		return string(b)
	}
	return string(b[:n]) + "…"
}
```

## Sample input

`testdata/sample_input.jsonl`:

```jsonl
{"method":"GET","path":"/health"}
{"method":"POST","path":"/api/v1/echo","body":{"greeting":"hello"},"headers":{"X-Trace-Id":"smoke-1"}}
{"path":"/api/v1/echo","body":{"greeting":"defaults to -method flag"}}
{"path":"/api/v1/lookup","query":{"id":"missing"},"skip_statuses":[404]}
["GET","/version"]
["POST","/api/v1/echo",{"greeting":"terse Mode B"}]
```

Row-level notes:

- Row 1: minimal GET, no body.
- Row 2: full JSON body plus per-row headers.
- Row 3: elides `method`, picks up whatever `-method` was set to.
- Row 4: a 404 here is a domain-level "no such record" — flagged as a
  skip, not a failure.
- Rows 5–6: Mode B terse form.

## Commands

```bash
# dry — decodes JSONL, no network
./smoke/bin/smoke -input=smoke/testdata/sample_input.jsonl -dry-run

# online — hits the staging server
./smoke/bin/smoke \
  -input=smoke/testdata/sample_input.jsonl \
  -base-url=https://api.staging.example.com \
  -method=POST \
  -timeout=10s \
  -header='X-Env:staging,Authorization:Bearer ${STAGING_TOKEN}'
```

Env-var expansion in flag values is the operator's responsibility —
the fish/bash shell does it before `main` sees the argv, so
`Authorization:Bearer ${STAGING_TOKEN}` becomes a literal token
before the binary reads it.

## Output shape

Given the sample input above, `results.jsonl` looks like:

```jsonl
{"line":1,"mode":"object","input":{"method":"GET","path":"/health"},"output":{"status":200,"status_text":"200 OK","headers":{"Content-Type":["application/json"]},"body":{"ok":true},"elapsed":"12ms"}}
{"line":2,"mode":"object","input":{"method":"POST","path":"/api/v1/echo","body":{"greeting":"hello"},"headers":{"X-Trace-Id":"smoke-1"}},"output":{"status":200,"status_text":"200 OK","headers":{"Content-Type":["application/json"]},"body":{"greeting":"hello"},"elapsed":"48ms"}}
```

`skipped.jsonl` picks up row 4 (with `skip_stage="run"`,
`skip_reason="status=404 (matches skip_statuses)"`). `failures.jsonl`
carries any row that returned an unaccepted status, complete with the
truncated body for diagnosis.

## Notes on scope

- **No retries.** If the operator wants retry-on-5xx behaviour, that
  logic goes into `Run` — but the default doesn't retry, because a
  smoke test is diagnostic. Retries hide the very signal you're
  trying to see.
- **No auth flow.** The `-header` flag covers static bearer / API-key
  auth. For OAuth handshakes or STS token refresh, add a
  `refreshToken` helper called from `Setup` and prepend the token to
  `adapterDefaultHeaders`.
- **No streaming.** `io.ReadAll` buffers the response body. For SSE
  or chunked-transfer endpoints, replace `Run` with a body-scanner
  loop and emit per-chunk records into `results.jsonl` — but at that
  point you're past the shape this recipe supports; consider whether
  a bespoke tool would be clearer.
- **No response schema validation.** The Output shape lands in
  `results.jsonl` as-is. Any downstream check (jq assertions,
  contract-test framework) runs against that file — decoupled from
  the smoke run, so a failing assertion doesn't kill the sweep.
