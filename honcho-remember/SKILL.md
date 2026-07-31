---
name: honcho-remember
description: Save conversation insights to long-term memory powered by Honcho. Use this skill whenever the user shares preferences, makes decisions, provides context about themselves or their projects, gives feedback on your behavior, or explicitly asks to remember something. Also fire this proactively when you notice important facts worth preserving — even if the user didn't ask. Trigger on phrases like "remember this", "I prefer", "always do X", "we decided", "from now on", or any time the user reveals a standing preference or project detail that would be useful in future sessions.
allowed-tools: Read, Bash
---

# Honcho Memory — Remember

Extract factual observations from the current conversation and save them to Honcho for long-term recall across sessions.

## When to Use

- User shares a preference ("I prefer functional style", "always use uv")
- User makes a decision ("we're going with PostgreSQL", "migrating to Vitest")
- User provides personal/project context ("I'm a backend engineer", "this repo uses monorepo")
- User gives feedback on your behavior ("don't summarize at the end", "keep responses short")
- User explicitly says "remember this" or similar
- You notice a fact worth preserving that the user hasn't explicitly asked you to save — don't wait to be told

## Extraction Rules

1. Extract ONLY facts about the user, their preferences, projects, or standing instructions
2. Each fact must be **atomic** — one idea per observation
3. Each fact must be **self-contained** — makes sense without surrounding context
4. Use **absolute dates** when possible (e.g., "June 26, 2025" not "yesterday")
5. **Attribute correctly**: "User prefers X" not just "X"
6. Do NOT extract:
   - Transient task details ("user asked me to fix a bug")
   - Your own responses or actions
   - Obvious facts that don't add value

## Process

1. Review the recent conversation and identify facts worth saving
2. Format observations as a JSON array of strings
3. Pipe the JSON to the save script

### Example observations:
```json
[
  "User prefers functional programming style over OOP",
  "User uses uv as their Python package manager",
  "User is migrating their test suite from Jest to Vitest as of April 2026",
  "User's project uses a monorepo structure with apps/ and packages/ directories",
  "INSTRUCTION: Do not add trailing summaries to responses"
]
```

### Save command:
```bash
echo '<json_array>' | python scripts/honcho_remember.py
```

The script saves observations to the currently active Honcho session (default: "global"). Session config lives in `~/.honcho/session.json` by default — use `/honcho-manage session map <name>` to change it.

## Troubleshooting

If the script fails with a **connection error**, Honcho is probably not running. Ask the user to run `/honcho-manage setup` to bootstrap the sidecar, then retry.

## Config Path Resolution

The script looks for `session.json` in this order:
1. `$HONCHO_HOME/` (if the env var is set)
2. Project-local `.claude/honcho/` (walk up from script dir)
3. `~/.honcho/` (global default)

This means cross-project memory works out of the box via `~/.honcho/`, and per-project overrides are still possible by placing a `.claude/honcho/` directory in the project root.

## Dependencies

- Python 3.10+
- Honcho sidecar running (see `/honcho-manage setup`)
- `~/.honcho/session.json` for session binding (auto-created by setup)
