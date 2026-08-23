#!/usr/bin/env node
// selftest.js — fixture-based smoke test for universal bailiff checks.
// Writes a temp tree, runs each checker against it, asserts hits and misses.
"use strict";

const fs = require("fs");
const os = require("os");
const path = require("path");
const assert = require("assert");

const localPaths = require("./check_local_paths");
const secrets = require("./check_secrets");
const prethink = require("./check_prethink");

function writeTree(root, files) {
  for (const [rel, body] of Object.entries(files)) {
    const abs = path.join(root, rel);
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    fs.writeFileSync(abs, body);
  }
}

function byCheck(findings, check) {
  return findings.filter((f) => f.check === check);
}

function hasMsg(findings, re) {
  return findings.some((f) => re.test(f.message) || re.test(f.code || ""));
}

// Partner-pattern tokens are joined at runtime so this file never contains a
// contiguous GitHub-push-protection match (ghp_, sk-, AKIA, PEM headers).
function fakeSecrets() {
  return {
    sk: ["sk", "abcdefghijklmnopqrstuvwxyz0123456789"].join("-"),
    akia: ["AKIA", "IOSFODNN7EXAMPLE"].join(""),
    ghp: ["ghp", "abcdefghijklmnopqrstuvwxyz0123456789"].join("_"),
    xoxb: ["xoxb", "1234567890", "abcdefghijklmnopqrstuv"].join("-"),
    pemOpen: ["-----BEGIN", "RSA PRIVATE KEY-----"].join(" "),
    pemClose: ["-----END", "RSA PRIVATE KEY-----"].join(" "),
  };
}

function main() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "bailiff-common-"));
  const fake = fakeSecrets();
  try {
    writeTree(root, {
      "bad/paths.go": [
        'package main',
        'var home = "/Users/carinae/Workspaces/tacit"',
        'var win = `C:\\Users\\carinae\\Documents\\app`',
        'var brew = "/opt/homebrew/bin/node"',
        'var rootHome = "/root/.ai/harness"',
        'var fileURL = "file:///Users/carinae/secret.txt"',
        "",
      ].join("\n"),
      "ok/paths.go": [
        "package main",
        'var bin = "/usr/bin/env"',
        'var tmp = "/tmp/data"',
        'var app = "/app/src/main.go"',
        'var example = "/Users/username/project"',
        'var generic = "/path/to/file"',
        'var linuxBin = "/bin/sh"',
        "",
      ].join("\n"),
      "bad/secrets.env": [
        `OPENAI_API_KEY=${fake.sk}`,
        `AWS_KEY=${fake.akia}`,
        `GITHUB_TOKEN=${fake.ghp}`,
        "DATABASE_URL=postgres://user:p@ssword@db.internal:5432/app",
        "HOOK=https://hooks.example.com/in?api_key=supersecretvalue",
        `SLACK=${fake.xoxb}`,
        "",
      ].join("\n"),
      "bad/secrets.go": [
        "package main",
        `var apiKey = "${fake.sk}"`,
        `const pem = \`${fake.pemOpen}`,
        "MIIEowIBAAKCAQEA",
        `${fake.pemClose}\``,
        "",
      ].join("\n"),
      "ok/secrets.go": [
        "package main",
        'apiKey := os.Getenv("API_KEY")',
        'var placeholder = "YOUR_API_KEY"',
        'var fromEnv = "${API_KEY}"',
        'var docs = "https://github.com/foo/bar"',
        "type Password string",
        'var parsed = map[string]string{}',
        'password := parsed["password"]',
        "",
      ].join("\n"),
      "ok/docstring.py": [
        'def parse(uri):',
        '    """Handles: postgresql+psycopg://user:pass@host:port/dbname"""',
        '    password = parsed["password"]',
        "    return uri",
        "",
      ].join("\n"),
      "ok/tokens.py": [
        "CSS = r'''",
        ":root {",
        "  --nd-black: #000000;",
        "  --nd-surface: #111111;",
        "  --nd-accent: #d71921;",
        "  --nd-success: #4a9e5c;",
        "  --nd-warning: #d4a843;",
        "}",
        "'''",
        "",
      ].join("\n"),
      "ok/secrets.env": [
        "API_KEY=${API_KEY}",
        "TOKEN=<token>",
        "PASSWORD=changeme",
        "",
      ].join("\n"),
      "bad/prethink.go": [
        "package main",
        "// we could have used Redis but the plan chose memory",
        "// originally we planned to fan this out as a worker pool",
        "// rejected because the other plan needed Kafka",
        "func run() {",
        "  if (false) {",
        "    leftover()",
        "  }",
        "}",
        "// func old() {",
        "//   x := 1",
        "//   y := 2",
        "//   return x + y",
        "//   fmt.Println(y)",
        "// }",
        "",
      ].join("\n"),
      "ok/prethink.go": [
        "package main",
        "// timeout is 3s per PRD §4",
        "// fallback to cache on handler error",
        "// Not Doing: see plan — this function is the chosen path",
        "func run() {}",
        "",
      ].join("\n"),
      ".claude/prds/demo.md": [
        "# PRD",
        "We considered Redis and rejected it because of ops cost.",
        "Alternatively we could have used SQLite.",
        "",
      ].join("\n"),
    });

    const args = (rel) => [path.join(root, rel)];
    const opts = { root };

    const pathBad = localPaths.main(args("bad/paths.go"), opts);
    const pathOk = localPaths.main(args("ok/paths.go"), opts);
    assert.ok(pathBad.length >= 4, `expected several local-path hits, got ${pathBad.length}`);
    assert.ok(
      pathBad.every((f) => f.code && !/carinae/.test(f.code)),
      "local-path findings must redact the username"
    );
    assert.strictEqual(pathOk.length, 0, `clean paths should be silent, got ${JSON.stringify(pathOk)}`);

    const secBadEnv = secrets.main(args("bad/secrets.env"), opts);
    const secBadGo = secrets.main(args("bad/secrets.go"), opts);
    const secOkGo = secrets.main(args("ok/secrets.go"), opts);
    const secOkEnv = secrets.main(args("ok/secrets.env"), opts);
    const secOkPy = secrets.main(args("ok/docstring.py"), opts);
    assert.ok(secBadEnv.length >= 4, `expected several secret hits in env, got ${secBadEnv.length}: ${JSON.stringify(secBadEnv)}`);
    assert.ok(secBadGo.length >= 2, `expected key + pem in go, got ${secBadGo.length}`);
    assert.ok(
      [...secBadEnv, ...secBadGo].every((f) => !JSON.stringify(f).includes(fake.sk)),
      "secret findings must redact literals"
    );
    assert.ok(hasMsg(secBadEnv, /credentials|secret parameter|Confidential|Sensitive assignment/i));
    assert.strictEqual(secOkGo.length, 0, `clean secrets.go should be silent, got ${JSON.stringify(secOkGo)}`);
    assert.strictEqual(secOkEnv.length, 0, `placeholder env should be silent, got ${JSON.stringify(secOkEnv)}`);
    assert.strictEqual(secOkPy.length, 0, `docstring/user:pass and parsed["password"] should be silent, got ${JSON.stringify(secOkPy)}`);

    const preBad = prethink.main(args("bad/prethink.go"), opts);
    const preOk = prethink.main(args("ok/prethink.go"), opts);
    const preCss = prethink.main(args("ok/tokens.py"), opts);
    const prePrd = prethink.main(args(".claude/prds/demo.md"), opts);
    assert.ok(preBad.length >= 3, `expected prethink hits, got ${preBad.length}: ${JSON.stringify(preBad)}`);
    assert.ok(byCheck(preBad, "prethink").length === preBad.length);
    assert.strictEqual(preOk.length, 0, `clean prethink should be silent, got ${JSON.stringify(preOk)}`);
    assert.strictEqual(preCss.length, 0, `CSS custom properties are not comments, got ${JSON.stringify(preCss)}`);
    assert.strictEqual(prePrd.length, 0, "PRDs must not be flagged for recording alternatives");

    process.stdout.write(`selftest ok (${root})\n`);
  } finally {
    fs.rmSync(root, { recursive: true, force: true });
  }
}

main();
