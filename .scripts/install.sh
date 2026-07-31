#!/usr/bin/env bash
# tacit-skills / install.sh
#
# Wire this repo's skills into one or more coding-CLI vendor directories, and
# install group-filtered policy files (CLAUDE.md, dev-routes.md) into each
# vendor's policy root. Interactive by default; every prompt has a flag for
# CI use. Idempotent: reruns are the upgrade path.
#
# Usage:
#   bash .scripts/install.sh                          # interactive install / sync
#   bash .scripts/install.sh --check                  # exit 0 if a rerun would be a no-op
#   bash .scripts/install.sh --dry-run                # show planned actions, no writes
#   bash .scripts/install.sh --yes                    # accept all prompt defaults
#   bash .scripts/install.sh --reconfigure            # re-run wiring/groups prompts
#   bash .scripts/install.sh --wired NAME[,NAME]      # non-interactive vendor selection
#   bash .scripts/install.sh --add-vendor NAME=PATH   # add custom vendor (repeatable)
#   bash .scripts/install.sh --policy-dir NAME=PATH   # override policy_dir (repeatable, empty = skip)
#   bash .scripts/install.sh --agents-dir NAME=PATH   # override agents_dir (repeatable, empty = skip)
#   bash .scripts/install.sh --no-policy              # skip policy install this run
#   bash .scripts/install.sh --no-agents              # skip agent-wrapper install this run
#   bash .scripts/install.sh --groups G1[,G2]         # non-interactive group selection
#   bash .scripts/install.sh --mode symlink|copy      # override install mode
#   bash .scripts/install.sh --enable-group NAME      # add group to existing config
#   bash .scripts/install.sh --disable-group NAME     # remove group, prune skills
#   bash .scripts/install.sh --uninstall              # remove all skills + policies + config
#   bash .scripts/install.sh --uninstall-vendor NAME  # remove just one vendor's stuff
#   bash .scripts/install.sh --force                  # overwrite conflicts (backs up)
#   bash .scripts/install.sh --run-migrator           # exec migrate-configs.py before install
#
# Config lives at ~/.config/tacit-skills/installer.yaml.
# Actions are logged to ~/.local/state/tacit-skills/install.log (JSON-Lines).

set -euo pipefail
IFS=$'\n\t'

# ---- preamble --------------------------------------------------------------

if [[ -z "${BASH_VERSION:-}" ]] || (( ${BASH_VERSION%%.*} < 4 )); then
    printf 'install: requires bash >= 4.0 (found: %s)\n' "${BASH_VERSION:-unknown}" >&2
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null || true)"
[[ -z "$REPO_ROOT" ]] && { printf 'install: run from a tacit-skills clone (git repo required)\n' >&2; exit 1; }

for bin in git ln readlink cp rm mkdir date awk sed sort; do
    command -v "$bin" >/dev/null 2>&1 || { printf 'install: missing required binary: %s\n' "$bin" >&2; exit 1; }
done

# ---- constants -------------------------------------------------------------

CFG_DIR="$HOME/.config/tacit-skills"
CFG="$CFG_DIR/installer.yaml"
CFG_HEADER="# tacit-skills installer.yaml v1"
LOG_DIR_DEFAULT="$HOME/.local/state/tacit-skills"
LOG_DEFAULT="$LOG_DIR_DEFAULT/install.log"
POLICY_HEADER_PREFIX="<!-- tacit-skills policy v1"
POLICY_FILES=(CLAUDE.md dev-routes.md)
AGENT_MARKER_PREFIX="<!-- tacit-skills agent v1"

# Built-in vendor defaults: name -> skills path / policy dir / agents dir
declare -A DEFAULT_VENDOR_SKILLS=(
    [claude]="$HOME/.claude/skills"
    [codex]="$HOME/.codex/skills"
)
declare -A DEFAULT_VENDOR_POLICY=(
    [claude]="$HOME/.claude"
    [codex]="$HOME/.codex"
)
declare -A DEFAULT_VENDOR_AGENTS=(
    [claude]="$HOME/.claude/agents"
    [codex]="$HOME/.codex/agents"
)
DEFAULT_VENDOR_ORDER=(claude codex)

# ---- utilities -------------------------------------------------------------

die()  { printf 'install: %s\n' "$*" >&2; exit 1; }
warn() { printf 'install: warn: %s\n' "$*" >&2; }
info() { printf 'install: %s\n' "$*"; }

# Ergonomic tilde expansion; also collapses $HOME back to ~ in output helpers.
expand_path() {
    local p="$1"
    p="${p/#\~/$HOME}"
    printf '%s' "$p"
}

collapse_home() {
    local p="$1"
    if [[ "$p" == "$HOME"* ]]; then
        printf '~%s' "${p#$HOME}"
    else
        printf '%s' "$p"
    fi
}

usage() {
    sed -n '2,32p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

iso8601_now() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }

# JSON string escape (for the log). Handles \ and ".
json_escape() {
    local s="$1"
    s="${s//\\/\\\\}"
    s="${s//\"/\\\"}"
    printf '%s' "$s"
}

# JSON array from bash array. Values are quoted+escaped.
json_array() {
    local -a items=("$@")
    local out="["
    local first=1
    for it in "${items[@]}"; do
        (( first )) || out+=","
        first=0
        out+="\"$(json_escape "$it")\""
    done
    out+="]"
    printf '%s' "$out"
}

# ---- arg parsing -----------------------------------------------------------

MODE=""                 # symlink|copy, from --mode; else config; else default 'symlink'
DO_CHECK=0
DO_DRY_RUN=0
DO_YES=0
DO_RECONFIGURE=0
DO_UNINSTALL=0
DO_FORCE=0
DO_NO_POLICY=0
DO_NO_AGENTS=0
DO_RUN_MIGRATOR=0
UNINSTALL_VENDOR=""
CLI_WIRED=""            # csv
CLI_GROUPS=""           # csv
CLI_ADD_VENDORS=()      # NAME=PATH
CLI_POLICY_DIRS=()      # NAME=PATH  (PATH may be empty)
CLI_AGENTS_DIRS=()      # NAME=PATH  (PATH may be empty)
ENABLE_GROUPS=()
DISABLE_GROUPS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check) DO_CHECK=1; shift ;;
        --dry-run) DO_DRY_RUN=1; shift ;;
        --yes) DO_YES=1; shift ;;
        --reconfigure) DO_RECONFIGURE=1; shift ;;
        --wired)
            [[ $# -lt 2 ]] && die "--wired requires an argument"
            CLI_WIRED="$2"; shift 2 ;;
        --add-vendor)
            [[ $# -lt 2 ]] && die "--add-vendor requires NAME=PATH"
            CLI_ADD_VENDORS+=("$2"); shift 2 ;;
        --policy-dir)
            [[ $# -lt 2 ]] && die "--policy-dir requires NAME=PATH"
            CLI_POLICY_DIRS+=("$2"); shift 2 ;;
        --agents-dir)
            [[ $# -lt 2 ]] && die "--agents-dir requires NAME=PATH"
            CLI_AGENTS_DIRS+=("$2"); shift 2 ;;
        --no-policy) DO_NO_POLICY=1; shift ;;
        --no-agents) DO_NO_AGENTS=1; shift ;;
        --groups)
            [[ $# -lt 2 ]] && die "--groups requires an argument"
            CLI_GROUPS="$2"; shift 2 ;;
        --mode)
            [[ $# -lt 2 ]] && die "--mode requires symlink|copy"
            MODE="$2"; shift 2
            [[ "$MODE" == "symlink" || "$MODE" == "copy" ]] || die "--mode must be symlink or copy"
            ;;
        --enable-group)
            [[ $# -lt 2 ]] && die "--enable-group requires a group name"
            ENABLE_GROUPS+=("$2"); shift 2 ;;
        --disable-group)
            [[ $# -lt 2 ]] && die "--disable-group requires a group name"
            DISABLE_GROUPS+=("$2"); shift 2 ;;
        --uninstall) DO_UNINSTALL=1; shift ;;
        --uninstall-vendor)
            [[ $# -lt 2 ]] && die "--uninstall-vendor requires a vendor name"
            UNINSTALL_VENDOR="$2"; shift 2 ;;
        --force) DO_FORCE=1; shift ;;
        --run-migrator) DO_RUN_MIGRATOR=1; shift ;;
        -h|--help) usage 0 ;;
        *) die "unknown arg: $1  (try --help)" ;;
    esac
done

# ---- skill discovery -------------------------------------------------------

list_skills() {
    local d name
    for d in "$REPO_ROOT"/*/; do
        [[ -d "$d" ]] || continue
        name="$(basename "$d")"
        [[ "$name" == .* ]] && continue
        [[ -f "$d/SKILL.md" ]] || continue
        printf '%s\n' "$name"
    done | sort
}

# Prefix rule: honcho-* -> vec-memory, else core. Any future skill that
# implements vector-backed persistent memory (regardless of the underlying
# tool) should be classified into the vec-memory group here.
skill_group() {
    case "$1" in
        honcho-*) printf 'vec-memory' ;;
        *)        printf 'core' ;;
    esac
}

# Agents live under .agents/*.md at the repo root. Same group prefix rule as
# skills applied to the .md basename.
list_agents() {
    local f name
    [[ -d "$REPO_ROOT/.agents" ]] || return 0
    for f in "$REPO_ROOT/.agents"/*.md; do
        [[ -f "$f" ]] || continue
        name="$(basename "$f" .md)"
        printf '%s\n' "$name"
    done | sort
}

agent_group() {
    case "$1" in
        honcho-*) printf 'vec-memory' ;;
        *)        printf 'core' ;;
    esac
}

# Pick the policy variant directory under .policy/ given the enabled groups.
# Current variants: core (default), vec-memory (when the vec-memory group is
# enabled). Reads CFG_GROUPS.
policy_variant() {
    local g
    for g in "${CFG_GROUPS[@]}"; do
        [[ "$g" == "vec-memory" ]] && { printf 'vec-memory'; return; }
    done
    printf 'core'
}

# ---- version resolution ----------------------------------------------------

current_version() {
    local v
    if v="$(git -C "$REPO_ROOT" describe --tags --exact-match HEAD 2>/dev/null)"; then
        printf '%s' "$v"; return
    fi
    if v="$(git -C "$REPO_ROOT" describe --tags --dirty 2>/dev/null)"; then
        printf '%s' "$v"; return
    fi
    local sha
    sha="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)"
    printf 'v0.0.0-%s' "$sha"
}

# Compare vA.B.C against vD.E.F (strip anything after the third number).
# Emits -1 | 0 | 1.
version_compare() {
    local a="$1" b="$2"
    a="${a#v}"; b="${b#v}"
    a="${a%%-*}"; b="${b%%-*}"     # drop -N-gSHA-dirty
    if [[ "$a" == "$b" ]]; then printf '0'; return; fi
    local first
    first="$(printf '%s\n%s\n' "$a" "$b" | sort -V | head -1)"
    if [[ "$first" == "$a" ]]; then printf -- '-1'; else printf '1'; fi
}

is_dev_build() {
    # HEAD not exactly on a tag = dev build.
    ! git -C "$REPO_ROOT" describe --tags --exact-match HEAD >/dev/null 2>&1
}

# ---- config I/O ------------------------------------------------------------

# Populated by read_config:
CFG_VERSION=""
CFG_REPO=""
CFG_MODE=""
CFG_LOG=""
CFG_LAST_RUN=""
CFG_VENDORS_NAME=()
CFG_VENDORS_PATH=()
CFG_VENDORS_POLICY=()
CFG_VENDORS_AGENTS=()
CFG_GROUPS=()
CFG_LOADED=0

reset_cfg_globals() {
    CFG_VERSION=""; CFG_REPO=""; CFG_MODE=""; CFG_LOG=""; CFG_LAST_RUN=""
    CFG_VENDORS_NAME=(); CFG_VENDORS_PATH=(); CFG_VENDORS_POLICY=(); CFG_VENDORS_AGENTS=()
    CFG_GROUPS=()
    CFG_LOADED=0
}

read_config() {
    reset_cfg_globals
    [[ -f "$CFG" ]] || return 0

    local first_line
    first_line="$(head -1 "$CFG")"
    if [[ "$first_line" != "$CFG_HEADER" ]]; then
        # Foreign file. Back up + treat as first-install.
        local bak="$CFG.bak.$(date +%s)"
        warn "existing $CFG has no tacit-skills header; backing up to $bak"
        mv "$CFG" "$bak"
        return 0
    fi

    # Two-phase parse:
    # 1) top-level scalars
    # 2) wired[] and groups[]
    local line key val
    local in_wired=0 in_groups=0
    local cur_name="" cur_path="" cur_policy="" cur_agents=""

    flush_vendor() {
        if [[ -n "$cur_name" ]]; then
            CFG_VENDORS_NAME+=("$cur_name")
            CFG_VENDORS_PATH+=("$cur_path")
            CFG_VENDORS_POLICY+=("$cur_policy")
            CFG_VENDORS_AGENTS+=("$cur_agents")
        fi
        cur_name=""; cur_path=""; cur_policy=""; cur_agents=""
    }

    while IFS= read -r line; do
        # Strip trailing CR (in case of dos line endings from an editor).
        line="${line%$'\r'}"
        [[ -z "$line" || "$line" =~ ^\# ]] && continue

        if [[ "$line" == "wired:" ]]; then
            in_wired=1; in_groups=0; continue
        fi
        if [[ "$line" == "groups:" ]]; then
            flush_vendor
            in_wired=0; in_groups=1; continue
        fi

        # Top-level scalar (no leading whitespace, has colon-space).
        if [[ "$line" =~ ^[a-z_]+:\ .+ ]] && [[ "$line" != " "* ]]; then
            flush_vendor
            in_wired=0; in_groups=0
            key="${line%%:*}"
            val="${line#*: }"
            case "$key" in
                version)  CFG_VERSION="$val" ;;
                repo)     CFG_REPO="$val" ;;
                mode)     CFG_MODE="$val" ;;
                log)      CFG_LOG="$val" ;;
                last_run) CFG_LAST_RUN="$val" ;;
            esac
            continue
        fi

        if (( in_wired )); then
            if [[ "$line" =~ ^\ *-\ name:\ (.+)$ ]]; then
                flush_vendor
                cur_name="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^\ +path:\ (.+)$ ]]; then
                cur_path="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^\ +policy_dir:\ (.*)$ ]]; then
                cur_policy="${BASH_REMATCH[1]}"
            elif [[ "$line" =~ ^\ +agents_dir:\ (.*)$ ]]; then
                cur_agents="${BASH_REMATCH[1]}"
            fi
            continue
        fi

        if (( in_groups )); then
            if [[ "$line" =~ ^\ *-\ (.+)$ ]]; then
                local gname="${BASH_REMATCH[1]}"
                # Legacy alias: 'honcho' → 'vec-memory'. Rewritten on next
                # write_config, so old installer.yaml files migrate silently.
                [[ "$gname" == "honcho" ]] && gname="vec-memory"
                CFG_GROUPS+=("$gname")
            fi
            continue
        fi
    done < "$CFG"

    flush_vendor
    CFG_LOADED=1
}

write_config() {
    mkdir -p "$CFG_DIR"
    local tmp="$CFG.tmp.$$"
    {
        printf '%s\n' "$CFG_HEADER"
        printf 'version: %s\n' "$CFG_VERSION"
        printf 'repo: %s\n' "$CFG_REPO"
        printf 'mode: %s\n' "$CFG_MODE"
        printf 'wired:\n'
        local i
        for (( i=0; i<${#CFG_VENDORS_NAME[@]}; i++ )); do
            printf '  - name: %s\n' "${CFG_VENDORS_NAME[$i]}"
            printf '    path: %s\n' "${CFG_VENDORS_PATH[$i]}"
            local pd="${CFG_VENDORS_POLICY[$i]:-}"
            if [[ -n "$pd" ]]; then
                printf '    policy_dir: %s\n' "$pd"
            fi
            local ad="${CFG_VENDORS_AGENTS[$i]:-}"
            if [[ -n "$ad" ]]; then
                printf '    agents_dir: %s\n' "$ad"
            fi
        done
        printf 'groups:\n'
        local g
        for g in "${CFG_GROUPS[@]}"; do
            printf '  - %s\n' "$g"
        done
        printf 'log: %s\n' "${CFG_LOG:-$LOG_DEFAULT}"
        printf 'last_run: %s\n' "$(iso8601_now)"
    } > "$tmp"
    mv "$tmp" "$CFG"
}

# ---- log -------------------------------------------------------------------

log_action() {
    local kv_json="$1"
    local logpath="${CFG_LOG:-$LOG_DEFAULT}"
    logpath="$(expand_path "$logpath")"
    mkdir -p "$(dirname "$logpath")"
    local ts; ts="$(iso8601_now)"
    printf '{"ts":"%s",%s}\n' "$ts" "$kv_json" >> "$logpath"
}

# ---- migrator coupling -----------------------------------------------------

MIGRATOR="$SCRIPT_DIR/migrate-configs.py"

check_migrator() {
    [[ -f "$MIGRATOR" ]] || return 0
    if ! command -v python3 >/dev/null 2>&1; then
        warn "python3 not found; skipping migrator pre-check"
        return 0
    fi
    if python3 "$MIGRATOR" --check >/dev/null 2>&1; then
        return 0
    fi
    if (( DO_RUN_MIGRATOR )); then
        info "running migrate-configs.py..."
        python3 "$MIGRATOR" || die "migrator failed"
        return 0
    fi
    warn "migrate-configs.py --check reports pending work:"
    python3 "$MIGRATOR" --check || true
    die "resolve migrator pending or re-run with --run-migrator"
}

# ---- policy writer ---------------------------------------------------------

# Write one policy file to the target with header + timestamp. The policy
# source is picked from the variant directory (.policy/<variant>/<file>) and
# copied verbatim — no filtering, no sentinels.
# Args: <src-file> <dst-file> <variant>
write_policy_file() {
    local src="$1" dst="$2" variant="$3"
    local tmp="$dst.tmp.$$"
    {
        printf '%s | variant: %s | generated: %s -->\n' "$POLICY_HEADER_PREFIX" "$variant" "$(iso8601_now)"
        cat "$src"
    } > "$tmp" || { rm -f "$tmp"; return 1; }
    mv "$tmp" "$dst"
}

# Write one agent wrapper to the target. The wrapper is a YAML-frontmattered
# markdown file; inject the tacit marker immediately after the closing `---`
# so vendor tools that parse the frontmatter still work, and reruns can
# distinguish ours from a user-authored agent with the same name.
# Args: <src-file> <dst-file>
write_agent_file() {
    local src="$1" dst="$2"
    local tmp="$dst.tmp.$$"
    local marker
    marker="$(printf '%s | generated: %s -->' "$AGENT_MARKER_PREFIX" "$(iso8601_now)")"
    awk -v marker="$marker" '
        BEGIN { fm_open=0; injected=0 }
        NR==1 && $0=="---" { fm_open=1; print; next }
        fm_open==1 && $0=="---" {
            print
            print marker
            fm_open=2; injected=1
            next
        }
        { print }
        END {
            if (!injected) {
                # No frontmatter close found; safer to bail than emit a broken file.
                exit 3
            }
        }
    ' "$src" > "$tmp"
    local rc=$?
    if (( rc != 0 )); then
        rm -f "$tmp"
        return $rc
    fi
    mv "$tmp" "$dst"
}

# Detect an existing tacit-managed agent file at $1. Returns 0 if the marker
# line is present anywhere in the first 20 lines.
is_our_agent_file() {
    head -n 20 "$1" 2>/dev/null | grep -q "^$AGENT_MARKER_PREFIX"
}

# ---- plan model ------------------------------------------------------------
#
# Plan is stored as bash arrays of records, one index per action:
#   PLAN_OP[i]       add | keep | prune | conflict
#                    | policy_add | policy_keep | policy_conflict
#                    | agent_add | agent_keep | agent_conflict | agent_prune
#   PLAN_VENDOR[i]   vendor name
#   PLAN_SKILL[i]    skill name (or POLICY/<file>, AGENT/<name>)
#   PLAN_TARGET[i]   absolute target path

PLAN_OP=()
PLAN_VENDOR=()
PLAN_SKILL=()
PLAN_TARGET=()

plan_add() { PLAN_OP+=("$1"); PLAN_VENDOR+=("$2"); PLAN_SKILL+=("$3"); PLAN_TARGET+=("$4"); }

# Build the (skill,vendor) plan given a list of vendors + enabled groups.
build_plan() {
    PLAN_OP=(); PLAN_VENDOR=(); PLAN_SKILL=(); PLAN_TARGET=()

    local -a skills=()
    while IFS= read -r s; do skills+=("$s"); done < <(list_skills)

    # Skills that should be present given enabled groups.
    local -A enabled_set=()
    local g
    for g in "${CFG_GROUPS[@]}"; do enabled_set[$g]=1; done

    local -a wanted_skills=()
    for s in "${skills[@]}"; do
        local grp; grp="$(skill_group "$s")"
        if [[ -n "${enabled_set[$grp]:-}" ]]; then
            wanted_skills+=("$s")
        fi
    done

    # For each vendor, plan actions.
    local i
    for (( i=0; i<${#CFG_VENDORS_NAME[@]}; i++ )); do
        local vname="${CFG_VENDORS_NAME[$i]}"
        local vpath; vpath="$(expand_path "${CFG_VENDORS_PATH[$i]}")"

        # Skill actions.
        local s target src
        for s in "${wanted_skills[@]}"; do
            target="$vpath/$s"
            src="$REPO_ROOT/$s"
            if [[ -L "$target" ]]; then
                local resolved; resolved="$(readlink "$target" || true)"
                if [[ "$resolved" == "$src" ]]; then
                    plan_add keep "$vname" "$s" "$target"
                else
                    plan_add conflict "$vname" "$s" "$target"
                fi
            elif [[ -e "$target" ]]; then
                # For copy mode with our marker: keep/upgrade. Otherwise conflict.
                if [[ "$CFG_MODE" == "copy" && -f "$target/.tacit-installed" ]]; then
                    plan_add keep "$vname" "$s" "$target"
                else
                    plan_add conflict "$vname" "$s" "$target"
                fi
            else
                plan_add add "$vname" "$s" "$target"
            fi
        done

        # Prune: anything currently in vpath that isn't wanted anymore.
        if [[ -d "$vpath" ]]; then
            local entry ename
            for entry in "$vpath"/*; do
                [[ -e "$entry" || -L "$entry" ]] || continue
                ename="$(basename "$entry")"
                # Skip anything already accounted for (keep/conflict).
                local accounted=0 j
                for (( j=0; j<${#PLAN_SKILL[@]}; j++ )); do
                    if [[ "${PLAN_VENDOR[$j]}" == "$vname" && "${PLAN_SKILL[$j]}" == "$ename" ]]; then
                        accounted=1; break
                    fi
                done
                (( accounted )) && continue

                # Is it "ours"? Symlink into REPO_ROOT, or copy-mode with marker.
                if [[ -L "$entry" ]]; then
                    local rl; rl="$(readlink "$entry" || true)"
                    if [[ "$rl" == "$REPO_ROOT/"* ]]; then
                        plan_add prune "$vname" "$ename" "$entry"
                    fi
                elif [[ -d "$entry" && -f "$entry/.tacit-installed" ]]; then
                    plan_add prune "$vname" "$ename" "$entry"
                fi
            done
        fi

        # Policy actions.
        local policy_dir="${CFG_VENDORS_POLICY[$i]:-}"
        if [[ -n "$policy_dir" && $DO_NO_POLICY -eq 0 ]]; then
            local pdir; pdir="$(expand_path "$policy_dir")"
            local pf
            for pf in "${POLICY_FILES[@]}"; do
                local ptarget="$pdir/$pf"
                if [[ -f "$ptarget" ]]; then
                    if head -1 "$ptarget" 2>/dev/null | grep -q "^$POLICY_HEADER_PREFIX"; then
                        plan_add policy_add "$vname" "POLICY/$pf" "$ptarget"    # always re-emit (timestamp)
                    else
                        plan_add policy_conflict "$vname" "POLICY/$pf" "$ptarget"
                    fi
                else
                    plan_add policy_add "$vname" "POLICY/$pf" "$ptarget"
                fi
            done
        fi

        # Agent actions. Agent wrappers install into agents_dir, gated on the
        # same group filter as skills. agents_dir defaults to
        # <policy_dir>/agents when unset; an explicit empty value skips agents
        # entirely (parallel to policy_dir behavior).
        local agents_dir="${CFG_VENDORS_AGENTS[$i]-__unset__}"
        if [[ "$agents_dir" == "__unset__" ]]; then
            if [[ -n "$policy_dir" ]]; then
                agents_dir="$policy_dir/agents"
            else
                agents_dir=""
            fi
        fi
        if [[ -n "$agents_dir" && $DO_NO_AGENTS -eq 0 ]]; then
            local adir; adir="$(expand_path "$agents_dir")"
            local -a all_agents=() wanted_agents=()
            while IFS= read -r a; do all_agents+=("$a"); done < <(list_agents)
            local a agrp
            for a in "${all_agents[@]}"; do
                agrp="$(agent_group "$a")"
                if [[ -n "${enabled_set[$agrp]:-}" ]]; then
                    wanted_agents+=("$a")
                fi
            done

            # Wanted agents -> add/keep/conflict.
            for a in "${wanted_agents[@]}"; do
                local atarget="$adir/$a.md"
                if [[ -f "$atarget" ]]; then
                    if is_our_agent_file "$atarget"; then
                        plan_add agent_add "$vname" "AGENT/$a" "$atarget"    # always re-emit (timestamp)
                    else
                        plan_add agent_conflict "$vname" "AGENT/$a" "$atarget"
                    fi
                else
                    plan_add agent_add "$vname" "AGENT/$a" "$atarget"
                fi
            done

            # Prune: tacit-managed agent files in $adir that aren't wanted.
            if [[ -d "$adir" ]]; then
                local aentry aename
                for aentry in "$adir"/*.md; do
                    [[ -f "$aentry" ]] || continue
                    aename="$(basename "$aentry" .md)"
                    local wanted=0 wa
                    for wa in "${wanted_agents[@]}"; do
                        [[ "$wa" == "$aename" ]] && { wanted=1; break; }
                    done
                    (( wanted )) && continue
                    if is_our_agent_file "$aentry"; then
                        plan_add agent_prune "$vname" "AGENT/$aename" "$aentry"
                    fi
                done
            fi
        fi
    done
}

# Pretty-print plan grouped by vendor.
print_plan() {
    if (( ${#PLAN_OP[@]} == 0 )); then
        info "no actions."
        return
    fi
    local color_reset="" c_add="" c_keep="" c_prune="" c_conflict=""
    if [[ -t 1 && -z "${NO_COLOR:-}" ]]; then
        color_reset=$'\033[0m'
        c_add=$'\033[32m'; c_keep=$'\033[2m'; c_prune=$'\033[33m'; c_conflict=$'\033[31m'
    fi

    local -A seen_vendor=()
    local i
    for (( i=0; i<${#PLAN_OP[@]}; i++ )); do
        local v="${PLAN_VENDOR[$i]}"
        if [[ -z "${seen_vendor[$v]:-}" ]]; then
            printf '\n  vendor: %s\n' "$v"
            seen_vendor[$v]=1
        fi
        local op="${PLAN_OP[$i]}"
        local marker c
        case "$op" in
            add)              marker='+ add     '; c="$c_add" ;;
            keep)             marker='= keep    '; c="$c_keep" ;;
            prune)            marker='- prune   '; c="$c_prune" ;;
            conflict)         marker='! conflict'; c="$c_conflict" ;;
            policy_add)       marker='+ policy  '; c="$c_add" ;;
            policy_keep)      marker='= policy  '; c="$c_keep" ;;
            policy_conflict)  marker='! policy!!'; c="$c_conflict" ;;
            agent_add)        marker='+ agent   '; c="$c_add" ;;
            agent_keep)       marker='= agent   '; c="$c_keep" ;;
            agent_prune)      marker='- agent   '; c="$c_prune" ;;
            agent_conflict)   marker='! agent!! '; c="$c_conflict" ;;
            *)                marker='? unknown '; c="" ;;
        esac
        printf '    %s%s%s  %-24s -> %s\n' "$c" "$marker" "$color_reset" "${PLAN_SKILL[$i]}" "$(collapse_home "${PLAN_TARGET[$i]}")"
    done
    printf '\n'
}

# Execute the plan.
execute_plan() {
    local added=0 pruned=0 conflicts=0 policy_written=0 agents_written=0 agents_pruned=0 backups=()
    local i
    for (( i=0; i<${#PLAN_OP[@]}; i++ )); do
        local op="${PLAN_OP[$i]}"
        local vname="${PLAN_VENDOR[$i]}"
        local sname="${PLAN_SKILL[$i]}"
        local target="${PLAN_TARGET[$i]}"

        case "$op" in
            keep) ;;
            add)
                mkdir -p "$(dirname "$target")"
                local src="$REPO_ROOT/$sname"
                if [[ "$CFG_MODE" == "copy" ]]; then
                    rm -rf "$target"
                    cp -R "$src" "$target"
                    : > "$target/.tacit-installed"
                else
                    ln -sfn "$src" "$target"
                fi
                added=$((added+1))
                ;;
            prune)
                if [[ -L "$target" ]]; then
                    rm -f "$target"
                elif [[ -d "$target" && -f "$target/.tacit-installed" ]]; then
                    rm -rf "$target"
                fi
                pruned=$((pruned+1))
                ;;
            conflict)
                if (( DO_FORCE )); then
                    local bak="$target.tacit-backup.$(date +%s)"
                    mv "$target" "$bak"
                    backups+=("$bak")
                    mkdir -p "$(dirname "$target")"
                    local src2="$REPO_ROOT/$sname"
                    if [[ "$CFG_MODE" == "copy" ]]; then
                        cp -R "$src2" "$target"
                        : > "$target/.tacit-installed"
                    else
                        ln -sfn "$src2" "$target"
                    fi
                    added=$((added+1))
                    warn "backed up conflicting $target -> $bak"
                else
                    conflicts=$((conflicts+1))
                fi
                ;;
            policy_add)
                # sname is "POLICY/<file>"
                local pf="${sname#POLICY/}"
                local variant; variant="$(policy_variant)"
                local src="$REPO_ROOT/.policy/$variant/$pf"
                if [[ ! -f "$src" ]]; then
                    warn "policy source missing: $src (skipping)"
                    continue
                fi
                mkdir -p "$(dirname "$target")"
                if write_policy_file "$src" "$target" "$variant"; then
                    policy_written=$((policy_written+1))
                else
                    die "policy write failed for $src"
                fi
                ;;
            policy_conflict)
                if (( DO_FORCE )); then
                    local bak2="$target.tacit-backup.$(date +%s)"
                    mv "$target" "$bak2"
                    backups+=("$bak2")
                    local pf2="${sname#POLICY/}"
                    local variant2; variant2="$(policy_variant)"
                    local src2="$REPO_ROOT/.policy/$variant2/$pf2"
                    write_policy_file "$src2" "$target" "$variant2"
                    policy_written=$((policy_written+1))
                    warn "backed up foreign policy $target -> $bak2"
                else
                    conflicts=$((conflicts+1))
                fi
                ;;
            agent_add)
                # sname is "AGENT/<name>"
                local aname="${sname#AGENT/}"
                local asrc="$REPO_ROOT/.agents/$aname.md"
                if [[ ! -f "$asrc" ]]; then
                    warn "agent source missing: $asrc (skipping)"
                    continue
                fi
                mkdir -p "$(dirname "$target")"
                if write_agent_file "$asrc" "$target"; then
                    agents_written=$((agents_written+1))
                else
                    die "agent write failed for $asrc (no frontmatter close?)"
                fi
                ;;
            agent_prune)
                rm -f "$target"
                agents_pruned=$((agents_pruned+1))
                ;;
            agent_conflict)
                if (( DO_FORCE )); then
                    local bak3="$target.tacit-backup.$(date +%s)"
                    mv "$target" "$bak3"
                    backups+=("$bak3")
                    local aname2="${sname#AGENT/}"
                    local asrc2="$REPO_ROOT/.agents/$aname2.md"
                    mkdir -p "$(dirname "$target")"
                    write_agent_file "$asrc2" "$target"
                    agents_written=$((agents_written+1))
                    warn "backed up foreign agent $target -> $bak3"
                else
                    conflicts=$((conflicts+1))
                fi
                ;;
        esac
    done

    if (( conflicts > 0 && ! DO_FORCE )); then
        printf 'install: %d conflict(s) — re-run with --force to overwrite (backups will be made)\n' "$conflicts" >&2
        return 3
    fi

    info "installed=$added pruned=$pruned policy=$policy_written agents=$agents_written agents_pruned=$agents_pruned"
    return 0
}

# Remove all policy files for a vendor that carry our header.
prune_policy_for_vendor() {
    local idx="$1"
    local policy_dir="${CFG_VENDORS_POLICY[$idx]:-}"
    [[ -z "$policy_dir" ]] && return 0
    local pdir; pdir="$(expand_path "$policy_dir")"
    local pf
    for pf in "${POLICY_FILES[@]}"; do
        local pt="$pdir/$pf"
        [[ -f "$pt" ]] || continue
        if head -1 "$pt" 2>/dev/null | grep -q "^$POLICY_HEADER_PREFIX"; then
            rm -f "$pt"
        fi
    done
}

# Remove all tacit-managed agent wrappers for a vendor.
prune_agents_for_vendor() {
    local idx="$1"
    local agents_dir="${CFG_VENDORS_AGENTS[$idx]-__unset__}"
    if [[ "$agents_dir" == "__unset__" ]]; then
        local policy_dir="${CFG_VENDORS_POLICY[$idx]:-}"
        if [[ -n "$policy_dir" ]]; then
            agents_dir="$policy_dir/agents"
        else
            return 0
        fi
    fi
    [[ -z "$agents_dir" ]] && return 0
    local adir; adir="$(expand_path "$agents_dir")"
    [[ -d "$adir" ]] || return 0
    local f
    for f in "$adir"/*.md; do
        [[ -f "$f" ]] || continue
        if is_our_agent_file "$f"; then
            rm -f "$f"
        fi
    done
    rmdir "$adir" 2>/dev/null || true
}

# Uninstall skills for a single vendor by index.
prune_all_for_vendor() {
    local idx="$1"
    local vname="${CFG_VENDORS_NAME[$idx]}"
    local vpath; vpath="$(expand_path "${CFG_VENDORS_PATH[$idx]}")"
    if [[ -d "$vpath" ]]; then
        local entry
        for entry in "$vpath"/*; do
            [[ -e "$entry" || -L "$entry" ]] || continue
            if [[ -L "$entry" ]]; then
                local rl; rl="$(readlink "$entry" || true)"
                if [[ "$rl" == "$REPO_ROOT/"* ]]; then rm -f "$entry"; fi
            elif [[ -d "$entry" && -f "$entry/.tacit-installed" ]]; then
                rm -rf "$entry"
            fi
        done
        # Remove empty skills dir.
        rmdir "$vpath" 2>/dev/null || true
    fi
    prune_policy_for_vendor "$idx"
    prune_agents_for_vendor "$idx"

    # If the vendor's policy_dir is now empty, remove it too.
    local policy_dir="${CFG_VENDORS_POLICY[$idx]:-}"
    if [[ -n "$policy_dir" ]]; then
        local pdir; pdir="$(expand_path "$policy_dir")"
        rmdir "$pdir" 2>/dev/null || true
    fi
}

# ---- interactive helpers ---------------------------------------------------

# Prompt for vendors. Populates CFG_VENDORS_* with the final selection.
# Existing config values are honored; --wired / --add-vendor override.
prompt_vendors() {
    # Build the candidate list (union of defaults, existing, add-vendor).
    local -a cand_name=() cand_path=() cand_policy=() cand_agents=()
    local -A idx_by_name=()

    add_cand() {
        local n="$1" p="$2" pol="$3" ag="$4"
        if [[ -n "${idx_by_name[$n]:-}" ]]; then
            local ci="${idx_by_name[$n]}"
            [[ -n "$p" ]] && cand_path[$ci]="$p"
            [[ -n "$pol" ]] && cand_policy[$ci]="$pol"
            [[ "$ag" != "__unset__" ]] && cand_agents[$ci]="$ag"
            return
        fi
        cand_name+=("$n"); cand_path+=("$p"); cand_policy+=("$pol")
        cand_agents+=("$ag")
        idx_by_name[$n]=$((${#cand_name[@]}-1))
    }

    # Built-in defaults.
    local d
    for d in "${DEFAULT_VENDOR_ORDER[@]}"; do
        add_cand "$d" "${DEFAULT_VENDOR_SKILLS[$d]}" "${DEFAULT_VENDOR_POLICY[$d]}" "${DEFAULT_VENDOR_AGENTS[$d]:-__unset__}"
    done
    # Existing config vendors.
    local i
    for (( i=0; i<${#CFG_VENDORS_NAME[@]}; i++ )); do
        local existing_ag="${CFG_VENDORS_AGENTS[$i]-__unset__}"
        add_cand "${CFG_VENDORS_NAME[$i]}" "${CFG_VENDORS_PATH[$i]}" "${CFG_VENDORS_POLICY[$i]:-}" "$existing_ag"
    done
    # --add-vendor entries.
    local pair
    for pair in "${CLI_ADD_VENDORS[@]:-}"; do
        [[ -z "$pair" ]] && continue
        [[ "$pair" =~ ^([A-Za-z0-9_-]+)=(.+)$ ]] || die "--add-vendor value must be NAME=PATH (got: $pair)"
        add_cand "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "" "__unset__"
    done
    # --policy-dir overrides.
    for pair in "${CLI_POLICY_DIRS[@]:-}"; do
        [[ -z "$pair" ]] && continue
        [[ "$pair" =~ ^([A-Za-z0-9_-]+)=(.*)$ ]] || die "--policy-dir value must be NAME=PATH (got: $pair)"
        local n="${BASH_REMATCH[1]}"
        local p="${BASH_REMATCH[2]}"
        if [[ -z "${idx_by_name[$n]:-}" ]]; then
            die "--policy-dir references unknown vendor '$n'"
        fi
        cand_policy[${idx_by_name[$n]}]="$p"
    done
    # --agents-dir overrides.
    for pair in "${CLI_AGENTS_DIRS[@]:-}"; do
        [[ -z "$pair" ]] && continue
        [[ "$pair" =~ ^([A-Za-z0-9_-]+)=(.*)$ ]] || die "--agents-dir value must be NAME=PATH (got: $pair)"
        local n="${BASH_REMATCH[1]}"
        local p="${BASH_REMATCH[2]}"
        if [[ -z "${idx_by_name[$n]:-}" ]]; then
            die "--agents-dir references unknown vendor '$n'"
        fi
        cand_agents[${idx_by_name[$n]}]="$p"
    done

    # Determine initial checked state.
    local -a checked=()
    if [[ -n "$CLI_WIRED" ]]; then
        # Non-interactive CSV.
        local -A picks=()
        local x rest="$CLI_WIRED"
        while [[ -n "$rest" ]]; do
            x="${rest%%,*}"
            picks[$x]=1
            if [[ "$rest" == "$x" ]]; then rest=""; else rest="${rest#*,}"; fi
        done
        for (( i=0; i<${#cand_name[@]}; i++ )); do
            if [[ -n "${picks[${cand_name[$i]}]:-}" ]]; then checked[$i]=1; else checked[$i]=0; fi
        done
    else
        for (( i=0; i<${#cand_name[@]}; i++ )); do
            local n="${cand_name[$i]}"
            local existed=0
            local j
            for (( j=0; j<${#CFG_VENDORS_NAME[@]}; j++ )); do
                if [[ "${CFG_VENDORS_NAME[$j]}" == "$n" ]]; then existed=1; break; fi
            done
            if (( existed )); then
                checked[$i]=1
            else
                # Pre-check if the parent dir already exists.
                local pth="${cand_path[$i]}"
                pth="$(expand_path "$pth")"
                local parent; parent="$(dirname "$pth")"
                if [[ -d "$parent" ]]; then checked[$i]=1; else checked[$i]=0; fi
            fi
        done
    fi

    # Non-interactive path.
    if (( DO_YES )) || [[ -n "$CLI_WIRED" ]]; then
        finalize_vendors cand_name cand_path cand_policy cand_agents checked
        return
    fi

    # Interactive loop.
    while :; do
        printf '\nWired vendors:\n'
        for (( i=0; i<${#cand_name[@]}; i++ )); do
            local mark; if [[ "${checked[$i]}" == "1" ]]; then mark='x'; else mark=' '; fi
            printf '  [%s] %d. %-16s -> %s\n' "$mark" $((i+1)) "${cand_name[$i]}" "$(collapse_home "${cand_path[$i]}")"
        done
        printf '  [a] add custom vendor\n'
        printf '  Toggle by number, "a" to add, Enter to confirm: '
        local answer
        read -r answer || answer=""
        if [[ -z "$answer" ]]; then break; fi
        if [[ "$answer" == "a" || "$answer" == "A" ]]; then
            printf '    Vendor name: '; local nn; read -r nn
            printf '    Skills path: '; local pp; read -r pp
            if [[ -z "$nn" || -z "$pp" ]]; then warn "empty name/path, aborting add"; continue; fi
            if [[ -n "${idx_by_name[$nn]:-}" ]]; then warn "vendor '$nn' already exists"; continue; fi
            add_cand "$nn" "$pp" "" "__unset__"
            checked+=("1")
            continue
        fi
        if [[ "$answer" =~ ^[0-9]+$ ]]; then
            local idx=$((answer-1))
            if (( idx >= 0 && idx < ${#cand_name[@]} )); then
                if [[ "${checked[$idx]}" == "1" ]]; then checked[$idx]=0; else checked[$idx]=1; fi
            fi
            continue
        fi
    done

    # Fill in policy_dir for newly-checked vendors that don't have one.
    for (( i=0; i<${#cand_name[@]}; i++ )); do
        if [[ "${checked[$i]}" == "1" && -z "${cand_policy[$i]}" ]]; then
            local n="${cand_name[$i]}"
            if [[ -n "${DEFAULT_VENDOR_POLICY[$n]:-}" ]]; then
                cand_policy[$i]="${DEFAULT_VENDOR_POLICY[$n]}"
            else
                printf '  Policy dir for %s (blank to skip): ' "$n"
                local pd; read -r pd
                cand_policy[$i]="$pd"
            fi
        fi
    done

    # Fill in agents_dir for newly-checked vendors when unset.
    # Interactive default: <policy_dir>/agents; blank input keeps default.
    for (( i=0; i<${#cand_name[@]}; i++ )); do
        if [[ "${checked[$i]}" == "1" && "${cand_agents[$i]}" == "__unset__" ]]; then
            local n="${cand_name[$i]}"
            if [[ -n "${DEFAULT_VENDOR_AGENTS[$n]:-}" ]]; then
                cand_agents[$i]="${DEFAULT_VENDOR_AGENTS[$n]}"
            elif [[ -n "${cand_policy[$i]}" ]]; then
                local default_ad="${cand_policy[$i]}/agents"
                printf '  Agents dir for %s (default: %s, blank to skip): ' "$n" "$(collapse_home "$default_ad")"
                local ad; read -r ad
                if [[ -z "$ad" ]]; then
                    cand_agents[$i]="$default_ad"
                else
                    cand_agents[$i]="$ad"
                fi
            else
                cand_agents[$i]=""
            fi
        fi
    done

    finalize_vendors cand_name cand_path cand_policy cand_agents checked
}

# Copy checked candidates into CFG_VENDORS_*.
finalize_vendors() {
    local -n _n=$1 _p=$2 _pol=$3 _ag=$4 _c=$5
    CFG_VENDORS_NAME=(); CFG_VENDORS_PATH=(); CFG_VENDORS_POLICY=(); CFG_VENDORS_AGENTS=()
    local i
    for (( i=0; i<${#_n[@]}; i++ )); do
        if [[ "${_c[$i]}" == "1" ]]; then
            CFG_VENDORS_NAME+=("${_n[$i]}")
            CFG_VENDORS_PATH+=("${_p[$i]}")
            local pol="${_pol[$i]:-}"
            # If policy_dir empty and it's a known-default vendor, apply default.
            if [[ -z "$pol" && -n "${DEFAULT_VENDOR_POLICY[${_n[$i]}]:-}" ]]; then
                pol="${DEFAULT_VENDOR_POLICY[${_n[$i]}]}"
            fi
            CFG_VENDORS_POLICY+=("$pol")
            # Resolve agents_dir. If still unset here, fall back to default or <policy>/agents.
            local ag="${_ag[$i]}"
            if [[ "$ag" == "__unset__" ]]; then
                if [[ -n "${DEFAULT_VENDOR_AGENTS[${_n[$i]}]:-}" ]]; then
                    ag="${DEFAULT_VENDOR_AGENTS[${_n[$i]}]}"
                elif [[ -n "$pol" ]]; then
                    ag="$pol/agents"
                else
                    ag=""
                fi
            fi
            CFG_VENDORS_AGENTS+=("$ag")
        fi
    done

    # Validate: no duplicate paths.
    local -A seen_path=()
    for (( i=0; i<${#CFG_VENDORS_PATH[@]}; i++ )); do
        local rp; rp="$(expand_path "${CFG_VENDORS_PATH[$i]}")"
        if [[ -n "${seen_path[$rp]:-}" ]]; then die "duplicate vendor path: $rp"; fi
        seen_path[$rp]=1
    done
}

prompt_groups() {
    # Determine target group set.
    if [[ -n "$CLI_GROUPS" ]]; then
        CFG_GROUPS=(core)
        local g rest="$CLI_GROUPS"
        while [[ -n "$rest" ]]; do
            g="${rest%%,*}"
            if [[ "$rest" == "$g" ]]; then rest=""; else rest="${rest#*,}"; fi
            [[ "$g" == "honcho" ]] && g="vec-memory"    # legacy alias
            if [[ "$g" != "core" ]]; then CFG_GROUPS+=("$g"); fi
        done
        return
    fi

    if (( DO_YES )); then
        # Keep whatever's in config, or default to core-only.
        if [[ ${#CFG_GROUPS[@]} -eq 0 ]]; then CFG_GROUPS=(core); fi
        return
    fi

    # Interactive: core is always in; only prompt for vec-memory.
    # Detect prior vec-memory membership (or legacy 'honcho' entries) from the
    # on-disk config. CFG_GROUPS has already been reset by an earlier
    # reconfigure path; the file is source of truth.
    local pre_vec=0
    if [[ -f "$CFG" ]] && grep -qE '^\s*-\s+(vec-memory|honcho)\s*$' "$CFG" 2>/dev/null; then
        pre_vec=1
    fi
    CFG_GROUPS=(core)

    local default_ans="N"; (( pre_vec )) && default_ans="Y"
    local prompt_str
    if [[ "$default_ans" == "Y" ]]; then
        prompt_str='Install vec-memory skills (long-term persistent memory, requires the underlying memory server)? [Y/n] '
    else
        prompt_str='Install vec-memory skills (long-term persistent memory, requires the underlying memory server)? [y/N] '
    fi
    printf '%s' "$prompt_str"
    local ans; read -r ans || ans=""
    ans="${ans:-$default_ans}"
    case "$ans" in
        y|Y|yes|YES) CFG_GROUPS+=(vec-memory) ;;
    esac
}

prompt_confirm_plan() {
    if (( DO_YES )); then return 0; fi
    printf 'Proceed? [Y/n] '
    local a; read -r a || a=""
    a="${a:-Y}"
    case "$a" in
        y|Y|yes|YES) return 0 ;;
        *) return 1 ;;
    esac
}

# ---- main dispatch ---------------------------------------------------------

migrator_pre_check() { check_migrator; }

# --check subcommand: report drift that a rerun would resolve.
# Symlink mode: only skill-set changes and policy staleness matter — git pull
# already handles content updates. Copy mode: version drift matters too because
# copies don't auto-update on git pull.
# Exit 0 = in sync; non-zero = a rerun would change something.
do_check() {
    read_config
    local cur; cur="$(current_version)"
    if (( ! CFG_LOADED )); then
        info "not installed (no ${CFG})"
        info "repo version: $cur"
        return 1
    fi

    # Skill-set / policy drift is what a plain rerun would fix.
    build_plan
    local skill_diffs=0 policy_diffs=0 agent_diffs=0 agent_prunes=0 conflicts=0 i
    for (( i=0; i<${#PLAN_OP[@]}; i++ )); do
        case "${PLAN_OP[$i]}" in
            add|prune)          skill_diffs=$((skill_diffs+1)) ;;
            conflict)           conflicts=$((conflicts+1)) ;;
            policy_add)         policy_diffs=$((policy_diffs+1)) ;;    # always re-emitted for timestamp
            policy_conflict)    conflicts=$((conflicts+1)) ;;
            agent_add)          agent_diffs=$((agent_diffs+1)) ;;       # always re-emitted (timestamp)
            agent_prune)        agent_prunes=$((agent_prunes+1)) ;;
            agent_conflict)     conflicts=$((conflicts+1)) ;;
        esac
    done

    # Version compare is only meaningful in copy mode.
    local version_drifted=0
    if [[ "${CFG_MODE:-symlink}" == "copy" && -n "$CFG_VERSION" && "$CFG_VERSION" != "$cur" ]]; then
        local base_a="${CFG_VERSION%%-*}"; base_a="${base_a#v}"
        local base_b="${cur%%-*}";         base_b="${base_b#v}"
        [[ "$base_a" != "$base_b" ]] && version_drifted=1
    fi

    info "repo version: $cur"
    info "installed:    ${CFG_VERSION:-<unset>}"
    info "mode:         ${CFG_MODE:-symlink}"

    local out_of_sync=0
    if (( skill_diffs > 0 )); then
        info "skill-set drift: $skill_diffs symlink(s) to add or prune — rerun to sync"
        out_of_sync=1
    fi
    if (( policy_diffs > 0 )); then
        info "policy files: $policy_diffs would be re-emitted (timestamp refresh)"
    fi
    if (( agent_diffs > 0 )); then
        info "agent wrappers: $agent_diffs would be re-emitted (timestamp refresh)"
    fi
    if (( agent_prunes > 0 )); then
        info "agent wrappers: $agent_prunes stale to prune — rerun to sync"
        out_of_sync=1
    fi
    if (( conflicts > 0 )); then
        info "conflicts: $conflicts (rerun with --force to overwrite, backups made)"
        out_of_sync=1
    fi
    if (( version_drifted )); then
        info "version drift (copy mode): $CFG_VERSION -> $cur — rerun to re-copy skills"
        out_of_sync=1
    fi

    if (( out_of_sync == 0 && skill_diffs == 0 && conflicts == 0 && ! version_drifted )); then
        info "in sync."
        return 0
    fi
    return 1
}

# --uninstall: nuke everything.
do_uninstall() {
    read_config
    if (( ! CFG_LOADED )); then
        info "no config; nothing to uninstall"
        return 0
    fi
    local i
    for (( i=0; i<${#CFG_VENDORS_NAME[@]}; i++ )); do
        info "removing vendor '${CFG_VENDORS_NAME[$i]}'..."
        (( DO_DRY_RUN )) || prune_all_for_vendor "$i"
    done
    (( DO_DRY_RUN )) || rm -f "$CFG"
    log_action "\"action\":\"uninstall\",\"vendors\":$(json_array "${CFG_VENDORS_NAME[@]}")"
    info "uninstalled."
}

# --uninstall-vendor NAME: prune just one.
do_uninstall_vendor() {
    read_config
    if (( ! CFG_LOADED )); then die "no installer.yaml"; fi
    local target="$UNINSTALL_VENDOR"
    local found=-1 i
    for (( i=0; i<${#CFG_VENDORS_NAME[@]}; i++ )); do
        if [[ "${CFG_VENDORS_NAME[$i]}" == "$target" ]]; then found=$i; break; fi
    done
    (( found < 0 )) && die "vendor '$target' not in config"

    (( DO_DRY_RUN )) || prune_all_for_vendor "$found"

    if (( ! DO_DRY_RUN )); then
        # Rebuild CFG_VENDORS_* without the removed one.
        local -a nn=() pp=() pol=()
        for (( i=0; i<${#CFG_VENDORS_NAME[@]}; i++ )); do
            if [[ $i -ne $found ]]; then
                nn+=("${CFG_VENDORS_NAME[$i]}")
                pp+=("${CFG_VENDORS_PATH[$i]}")
                pol+=("${CFG_VENDORS_POLICY[$i]:-}")
            fi
        done
        CFG_VENDORS_NAME=("${nn[@]}"); CFG_VENDORS_PATH=("${pp[@]}"); CFG_VENDORS_POLICY=("${pol[@]}")
        CFG_VERSION="$(current_version)"; CFG_REPO="$REPO_ROOT"
        [[ -z "$CFG_MODE" ]] && CFG_MODE="symlink"
        write_config
    fi
    log_action "\"action\":\"uninstall-vendor\",\"vendor\":\"$(json_escape "$target")\""
    info "removed vendor '$target'."
}

# The main install/upgrade path.
do_install() {
    read_config

    local prior_version="$CFG_VERSION"
    local prior_groups="${CFG_GROUPS[*]:-}"

    # Resolve mode.
    if [[ -z "$MODE" ]]; then
        MODE="${CFG_MODE:-symlink}"
    fi
    CFG_MODE="$MODE"

    # Reconfigure or first-run forces prompts.
    local first_run=0
    (( CFG_LOADED )) || first_run=1

    if (( DO_RECONFIGURE || first_run )); then
        prompt_vendors
        prompt_groups
    else
        # Non-reconfigure runs still need to apply --add-vendor / --policy-dir / --wired.
        if (( ${#CLI_ADD_VENDORS[@]} > 0 )) || (( ${#CLI_POLICY_DIRS[@]} > 0 )) || [[ -n "$CLI_WIRED" ]]; then
            prompt_vendors
        fi
        # Group toggles.
        apply_group_toggles
    fi

    # If groups is empty (e.g. reset), default to core.
    if (( ${#CFG_GROUPS[@]} == 0 )); then CFG_GROUPS=(core); fi

    # Set version + repo.
    CFG_VERSION="$(current_version)"
    CFG_REPO="$REPO_ROOT"
    [[ -z "$CFG_LOG" ]] && CFG_LOG="$LOG_DEFAULT"

    if [[ ${#CFG_VENDORS_NAME[@]} -eq 0 ]]; then
        info "no vendors selected; nothing to do."
        return 0
    fi

    build_plan

    if (( DO_DRY_RUN )); then
        info "dry-run — planned actions:"
        print_plan
        return 0
    fi

    print_plan
    if ! prompt_confirm_plan; then
        info "aborted."
        return 1
    fi

    execute_plan || return $?

    write_config

    # Log summary.
    local action="install"
    [[ -n "$prior_version" ]] && action="upgrade"
    local vendors_json; vendors_json="$(json_array "${CFG_VENDORS_NAME[@]}")"
    local groups_json;  groups_json="$(json_array "${CFG_GROUPS[@]}")"
    local kv
    if [[ "$action" == "upgrade" ]]; then
        kv="\"action\":\"upgrade\",\"version\":\"$(json_escape "$CFG_VERSION")\",\"from\":\"$(json_escape "$prior_version")\",\"vendors\":$vendors_json,\"groups\":$groups_json,\"mode\":\"$(json_escape "$CFG_MODE")\""
    else
        kv="\"action\":\"install\",\"version\":\"$(json_escape "$CFG_VERSION")\",\"vendors\":$vendors_json,\"groups\":$groups_json,\"mode\":\"$(json_escape "$CFG_MODE")\""
    fi
    log_action "$kv"

    info "done. Config at $CFG"

    # vec-memory note if newly enabled.
    local g had_vec_before=0 has_vec_now=0
    if [[ "$prior_groups" == *"vec-memory"* || "$prior_groups" == *"honcho"* ]]; then had_vec_before=1; fi
    for g in "${CFG_GROUPS[@]}"; do [[ "$g" == "vec-memory" ]] && has_vec_now=1; done
    if (( has_vec_now && ! had_vec_before )); then
        info "vec-memory enabled — set up the memory server via the 'honcho-manage' skill."
    fi
}

apply_group_toggles() {
    local -A gset=()
    local g
    if (( ${#CFG_GROUPS[@]} > 0 )); then
        for g in "${CFG_GROUPS[@]}"; do gset[$g]=1; done
    fi
    if (( ${#ENABLE_GROUPS[@]} > 0 )); then
        for g in "${ENABLE_GROUPS[@]}"; do
            [[ "$g" == "honcho" ]] && g="vec-memory"     # legacy alias
            gset[$g]=1
        done
    fi
    if (( ${#DISABLE_GROUPS[@]} > 0 )); then
        for g in "${DISABLE_GROUPS[@]}"; do
            [[ "$g" == "honcho" ]] && g="vec-memory"     # legacy alias
            unset 'gset[$g]' 2>/dev/null || true
        done
    fi
    gset[core]=1  # core is always on
    CFG_GROUPS=()
    for g in "${!gset[@]}"; do CFG_GROUPS+=("$g"); done
}

# ---- entry point -----------------------------------------------------------

if (( DO_CHECK )); then
    do_check
    exit $?
fi

migrator_pre_check

if (( DO_UNINSTALL )); then
    do_uninstall
    exit 0
fi

if [[ -n "$UNINSTALL_VENDOR" ]]; then
    do_uninstall_vendor
    exit 0
fi

do_install
