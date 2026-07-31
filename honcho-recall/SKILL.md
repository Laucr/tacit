---
name: honcho-recall
description: Recall stored knowledge about the user from long-term memory powered by Honcho. Use this skill when you need context about the user's preferences, past decisions, technical background, project details, or standing instructions. Also use proactively at the start of complex tasks to check for relevant prior context before diving in. Trigger when the user asks "what do you know about me?", "didn't I tell you about X?", "what did we decide?", or when you're about to suggest a tool, framework, or approach and want to check if the user has a known preference. Use it at the beginning of new sessions to personalize your behavior.
allowed-tools: Bash
---

# Honcho Memory — Recall

Query Honcho to retrieve relevant observations about the user from long-term memory.

## When to Use

- **Start of complex tasks**: Before diving in, run a broad recall query to pick up preferences, standing instructions, or past decisions that might be relevant. This is one of the most valuable uses — don't skip it.
- **User asks about past context**: "What did we decide about X?", "Didn't I tell you my preference?", "What do you know about me?"
- **Personalizing behavior**: When you're about to suggest a tool, framework, style, or approach — check if the user has a known preference first.
- **Cross-session continuity**: When context from a previous session might be relevant to the current task.
- **New session startup**: Consider a broad recall early in a session to pick up standing instructions and preferences.

## Process

1. Formulate a search query that describes the context you need
2. Run the recall script with the query as argument
3. Use the returned observations to inform your response

### Query examples:
```bash
# Specific topic
python scripts/honcho_recall.py "user's preferred programming languages and tools"

# Broad recall (good for start-of-task context)
python scripts/honcho_recall.py "user preferences and standing instructions"

# Project-specific
python scripts/honcho_recall.py "current project architecture decisions"

# List all recent memories
python scripts/honcho_recall.py --list
```

The script searches the currently active Honcho session (default: "global") using semantic similarity. If no semantic matches are found, it falls back to listing recent observations.

## Using the Results

- Observations are returned as a markdown list
- Each observation includes its session scope and creation date
- Use observations as context — don't repeat them verbatim to the user unless asked
- If observations conflict with the current conversation, **prefer the current conversation** (memories may be outdated)
- If a memory seems stale or wrong, consider using `/honcho-manage forget` to clean it up

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
