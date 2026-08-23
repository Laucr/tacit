# Universal Static Checks

Language-independent hygiene checks. These run on **every** bailiff pass, including projects that have no language-specific checker.

They catch things compile and CI usually miss: a developer's home path pasted into source, a token committed into `.claude/` or a tracked file, leftover comments that narrate an unchosen plan.

Scripts are plain JavaScript (Node.js) — no compilation, no dependencies.

## Checks

| Check | Script | What it catches |
|---|---|---|
| Local paths | `scripts/common/check_local_paths.js` | Machine-local filesystem paths (`/Users/<name>/…`, `/home/<name>/…`, `C:\Users\…`, `/opt/homebrew/…`, `/root/…`, `file:///Users/…`) leaked into the tree |
| Secrets | `scripts/common/check_secrets.js` | Tokens, API keys, private key blocks, `user:password@` URLs, secret query parameters, hardcoded private/internal URLs, sensitive assignments (`api_key = "…"`, `.env` literals) |
| Pre-thinking | `scripts/common/check_prethink.js` | Comments and dead code that recap unchosen paths, rejected plans, "we could have used X", commented-out implementations, `if (false)` / `#if 0` gates |

## Scan scope

With **no file arguments**, each script scans:

1. Every path `git ls-files` reports (VCS-included).
2. Harness directories even when gitignored: `.claude/`, `.agent/`, `.agents/`.

That is deliberate. Secrets and local paths leak from files the current feature did not touch, and agent dumps under `.claude/` are a common source.

With file or directory arguments, only those paths are scanned (directories are walked).

Skipped regardless of scope: `node_modules/`, `vendor/`, VCS lockfiles, binaries, generated files (`Code generated` / `@generated` headers), files larger than 1 MiB.

`check_prethink.js` additionally skips `.claude/prds/`, `.claude/plans/`, `.claude/reports/`, and `.claude/amendments/` — those documents are supposed to record alternatives — and only inspects source files, not markdown.

## How to Run

From the project being verified, invoke via the skill's script path:

```bash
node <bailiff>/scripts/common/check_local_paths.js
node <bailiff>/scripts/common/check_secrets.js
node <bailiff>/scripts/common/check_prethink.js
```

Or restrict to an explicit set:

```bash
node <bailiff>/scripts/common/check_secrets.js .claude cmd/
node <bailiff>/scripts/common/check_local_paths.js ./path/to/file.go
```

Run all three:

```bash
for check in <bailiff>/scripts/common/check_*.js; do
  node "$check"
done
```

Self-test (from the skill directory):

```bash
node scripts/common/selftest.js
```

## Output Format

Same JSON-lines contract as the Go checks. One object per finding on stdout:

```json
{"file": "cmd/server.go", "line": 42, "severity": "warning", "check": "local_paths", "message": "Machine-local home path — replace with a relative path or config: /Users/***/proj", "code": "root := \"/Users/***/proj\""}
```

Exit code: `0` = no findings, `1` = findings present.

`check` values: `local_paths`, `secrets`, `prethink`.

Severity:

- `error` — Must fix. A committed secret, credentialed URL, or private key. **Error-severity static findings are Failures** and prevent a PASS verdict.
- `warning` — Should fix. Local paths, internal URLs, leftover pre-thinking comments, dead gates.
- `info` — Worth reviewing.

Secret findings **redact** the literal in `code` and `message` (`***REDACTED***`, usernames in paths become `***`). Do not copy the raw secret into the bailiff report.

## When to Skip / Allow

- **Placeholder values**: `YOUR_API_KEY`, `changeme`, `${API_KEY}`, `<token>`, `os.Getenv("…")` are not findings.
- **Placeholder users in paths**: `/Users/username/`, `/Users/alice/`, `/path/to/…` are not findings.
- **Portable paths**: `/usr/bin`, `/tmp/…`, `/app/…`, `/var/log/…` are not findings.
- **Public URLs**: `github.com`, `example.com`, `golang.org`, and similar docs hosts are not internal-URL findings. `user:pass@` and `?api_key=` still are, on any host.
- **Plans and PRDs**: alternatives belong there; prethink does not scan them.
- **Test files**: secrets in tests are still errors if the value looks real. Local-path and prethink warnings still apply.

## Adding New Universal Checks

1. Create `scripts/common/check_<name>.js`.
2. Same CLI: optional file args, JSON lines on stdout, exit 0/1. Reuse `scripts/common/lib.js` for discovery.
3. Add a row to the table above.
4. Extend `scripts/common/selftest.js` with a positive and a negative fixture. Assemble partner-pattern tokens (`ghp_`, `sk-`, `AKIA`, PEM headers) at runtime — never as contiguous literals, or GitHub push protection will block the push.
