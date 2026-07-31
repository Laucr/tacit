---
name: honcho-manage
description: Manage the Honcho memory system — setup, health checks, session management, and memory deletion. Use this skill when the user wants to set up memory for the first time, check if memory is working, switch between memory sessions (e.g., per-project scoping), delete or forget specific memories, or troubleshoot connection issues. Also trigger when the user mentions "honcho", "memory setup", "forget a memory", "switch session", "memory status", or asks why remember/recall isn't working.
allowed-tools: Read, Write, Bash
---

# Honcho Memory — Manage

Administrative operations for the Honcho memory sidecar. This is the "control panel" for the memory system — use it for first-time setup, health checks, session scoping, and memory cleanup.

> **Why does this skill need Write permission?** The `session map` subcommand writes `.claude/honcho/session.json` to persist the active session binding.

## Subcommands

| Command | Description |
|---|---|
| `setup` | First-time bootstrap: provision database, start Docker sidecar, create workspace and peers |
| `status` | Health check: is Honcho running? Show active session and observation count |
| `session map <name>` | Bind current context to a named Honcho session (e.g., `session map my-project`) |
| `session list` | List all Honcho sessions |
| `session show <name>` | Show details for a specific session |
| `forget <id>` | Delete a specific observation by its ID |
| `forget --query <q>` | Search for observations matching a query (shows matches, then delete by ID) |
| `forget --session <name>` | Wipe ALL observations for a session |
| `config show` | Show current Honcho connection configuration |

## Usage

Run subcommands via the manage script:

```bash
# First-time setup (start sidecar, provision DB, create workspace)
python scripts/honcho_manage.py setup

# Check health
python scripts/honcho_manage.py status

# Bind to a project session
python scripts/honcho_manage.py session map my-project

# Switch back to global session
python scripts/honcho_manage.py session map global

# List sessions
python scripts/honcho_manage.py session list

# Forget a specific memory
python scripts/honcho_manage.py forget <conclusion-id>

# Find and forget memories about a topic
python scripts/honcho_manage.py forget --query "old project preferences"

# Wipe a session's memories
python scripts/honcho_manage.py forget --session old-project

# Show connection config
python scripts/honcho_manage.py config show
```

## Prerequisites

- **Docker** installed and running (for the Honcho sidecar container)
- **PostgreSQL** with pgvector extension available (the setup command will provision the database if `psql` or `psycopg` is available)
- `~/.honcho/.env` configured with connection strings (copy from `.env.example` if not yet set up)

## Config Path Resolution

All honcho scripts resolve the config directory in this order:
1. `$HONCHO_HOME/` (if the env var is set)
2. Project-local `.claude/honcho/` (walk up from script dir)
3. **`~/.honcho/`** (global default — created by `setup`)

The global default (`~/.honcho/`) is the recommended path because honcho's purpose is cross-session, cross-project memory. Per-project overrides via `.claude/honcho/` are still supported for advanced use cases.

## Session Mapping

Sessions scope your memories so you can keep project-specific knowledge separate from general preferences.

- **`global`** (default): Cross-project knowledge — preferences, standing instructions, personal context
- **`<project-name>`**: Project-specific decisions, architecture choices, team conventions

Use `session map <name>` to scope subsequent `/honcho-remember` and `/honcho-recall` to a specific project. Use `session map global` to switch back. The binding persists in `session.json` inside the config directory and is picked up by the remember and recall scripts automatically.

## Dependencies

- Python 3.10+
- Docker (for sidecar container)
- PostgreSQL with pgvector (database backend)
