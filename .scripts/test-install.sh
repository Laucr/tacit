#!/usr/bin/env bash
# tacit-skills / test-install.sh
#
# Smoke harness for install.sh + release.sh. Each scenario runs in an isolated
# temp HOME. Prints PASS / FAIL per scenario; exits non-zero if any fail.
#
# Usage:
#   bash .scripts/test-install.sh
#   bash -x .scripts/test-install.sh   # debug mode

set -uo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTALL="$SCRIPT_DIR/install.sh"
RELEASE="$SCRIPT_DIR/release.sh"

pass_count=0
fail_count=0
CURRENT_SCENARIO=""

announce() {
    CURRENT_SCENARIO="$1"
    printf '\n== %s\n' "$1"
}

pass() {
    printf '  PASS: %s\n' "$1"
    pass_count=$((pass_count+1))
}

fail() {
    printf '  FAIL: %s\n' "$1" >&2
    fail_count=$((fail_count+1))
}

assert_eq() {
    local expected="$1" actual="$2" label="$3"
    if [[ "$expected" == "$actual" ]]; then
        pass "$label ($expected)"
    else
        fail "$label — expected=$expected got=$actual"
    fi
}

assert_gt() {
    local threshold="$1" actual="$2" label="$3"
    if (( actual > threshold )); then
        pass "$label ($actual > $threshold)"
    else
        fail "$label — expected>$threshold got=$actual"
    fi
}

# Total core (non-honcho) skills in the repo.
count_core_skills() {
    local n=0 d name
    for d in "$REPO_ROOT"/*/; do
        [[ -d "$d" ]] || continue
        name="$(basename "$d")"
        [[ "$name" == .* ]] && continue
        [[ -f "$d/SKILL.md" ]] || continue
        [[ "$name" == honcho-* ]] && continue
        n=$((n+1))
    done
    printf '%d' "$n"
}

count_honcho_skills() {
    local n=0 d name
    for d in "$REPO_ROOT"/*/; do
        [[ -d "$d" ]] || continue
        name="$(basename "$d")"
        [[ "$name" == honcho-* && -f "$d/SKILL.md" ]] || continue
        n=$((n+1))
    done
    printf '%d' "$n"
}

# Count core (non-honcho-*) agent wrappers under .agents/.
count_core_agents() {
    local n=0 f name
    [[ -d "$REPO_ROOT/.agents" ]] || { printf '0'; return; }
    for f in "$REPO_ROOT/.agents"/*.md; do
        [[ -f "$f" ]] || continue
        name="$(basename "$f" .md)"
        [[ "$name" == honcho-* ]] && continue
        n=$((n+1))
    done
    printf '%d' "$n"
}

count_honcho_agents() {
    local n=0 f name
    [[ -d "$REPO_ROOT/.agents" ]] || { printf '0'; return; }
    for f in "$REPO_ROOT/.agents"/*.md; do
        [[ -f "$f" ]] || continue
        name="$(basename "$f" .md)"
        [[ "$name" == honcho-* ]] || continue
        n=$((n+1))
    done
    printf '%d' "$n"
}

CORE_N="$(count_core_skills)"
HONCHO_N="$(count_honcho_skills)"
CORE_AGENTS_N="$(count_core_agents)"
HONCHO_AGENTS_N="$(count_honcho_agents)"

# ---- Scenario 1: first-install core-only ----------------------------------
announce "Scenario 1: first-install core-only"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > "$SANDBOX/out" 2>&1
rc=$?
assert_eq 0 "$rc" "install exits 0"
n_links="$(find "$SANDBOX/.claude/skills" -maxdepth 1 -type l 2>/dev/null | wc -l)"
assert_eq "$CORE_N" "$n_links" "correct number of symlinked skills"
[[ -f "$SANDBOX/.claude/CLAUDE.md" ]] && pass "CLAUDE.md written" || fail "CLAUDE.md missing"
[[ -f "$SANDBOX/.claude/dev-routes.md" ]] && pass "dev-routes.md written" || fail "dev-routes.md missing"
SANDBOX1="$SANDBOX"

# ---- Scenario 2: rerun is idempotent --------------------------------------
announce "Scenario 2: rerun is idempotent"
HOME="$SANDBOX1" bash "$INSTALL" --yes --wired claude --groups core > "$SANDBOX1/rerun.out" 2>&1
rc=$?
assert_eq 0 "$rc" "rerun exits 0"
# skill symlinks: none added, none pruned.
if grep -q "installed=0 pruned=0" "$SANDBOX1/rerun.out"; then
    pass "rerun reports no skill changes"
else
    fail "rerun reports skill changes: $(grep 'installed=' "$SANDBOX1/rerun.out")"
fi

# ---- Scenario 3: enable-group vec-memory ----------------------------------
announce "Scenario 3: --enable-group vec-memory"
HOME="$SANDBOX1" bash "$INSTALL" --yes --enable-group vec-memory > "$SANDBOX1/enable.out" 2>&1
rc=$?
assert_eq 0 "$rc" "enable-group exits 0"
n_honcho="$(find "$SANDBOX1/.claude/skills" -maxdepth 1 -type l -name 'honcho-*' 2>/dev/null | wc -l)"
assert_eq "$HONCHO_N" "$n_honcho" "honcho symlinks present"

# ---- Scenario 4: uninstall-vendor -----------------------------------------
announce "Scenario 4: --uninstall-vendor claude"
HOME="$SANDBOX1" bash "$INSTALL" --uninstall-vendor claude > "$SANDBOX1/uninstall.out" 2>&1
rc=$?
assert_eq 0 "$rc" "uninstall exits 0"
[[ ! -e "$SANDBOX1/.claude/skills" ]] && pass "empty skills dir pruned" || fail "empty skills dir left behind"
[[ ! -f "$SANDBOX1/.claude/CLAUDE.md" ]] && pass "policy CLAUDE.md removed" || fail "policy CLAUDE.md still present"
[[ ! -e "$SANDBOX1/.claude" ]] && pass "empty policy dir pruned" || pass "policy dir has non-tacit content (kept)"

# ---- Scenario 5: real dir at target -> conflict ---------------------------
announce "Scenario 5: conflict on pre-existing real dir"
SANDBOX="$(mktemp -d)"
mkdir -p "$SANDBOX/.claude/skills/pivot"
echo "user data" > "$SANDBOX/.claude/skills/pivot/README.md"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > "$SANDBOX/out" 2>&1
rc=$?
if (( rc != 0 )); then pass "conflict returns non-zero (rc=$rc)"; else fail "conflict returned 0"; fi
grep -q "conflict" "$SANDBOX/out" && pass "conflict mentioned in output" || fail "no 'conflict' word in output"
[[ -f "$SANDBOX/.claude/skills/pivot/README.md" ]] && pass "user file preserved" || fail "user file lost"

# ---- Scenario 6: core variant has no honcho references -------------------
announce "Scenario 6: policy variant — core picks the honcho-less file"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > /dev/null 2>&1
n_honcho_refs="$(grep -c 'honcho-recall\|honcho-remember\|honcho-manage' "$SANDBOX/.claude/CLAUDE.md" "$SANDBOX/.claude/dev-routes.md" 2>/dev/null | awk -F: '{s+=$NF} END{print s+0}')"
assert_eq 0 "$n_honcho_refs" "no honcho references in core-variant policy"
n_route_refs="$(grep -c 'blueprint\|builder\|bailiff' "$SANDBOX/.claude/dev-routes.md" 2>/dev/null || echo 0)"
assert_gt 0 "$n_route_refs" "dev-routes.md retains non-honcho content"
grep -q 'variant: core' "$SANDBOX/.claude/CLAUDE.md" && pass "header records variant: core" || fail "no variant in header"

# ---- Scenario 7: vec-memory variant keeps honcho -------------------------
announce "Scenario 7: policy variant — vec-memory picks the honcho-aware file"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core,vec-memory > /dev/null 2>&1
n_full_honcho="$(grep -c 'honcho-recall\|honcho-remember\|honcho-manage' "$SANDBOX/.claude/CLAUDE.md" "$SANDBOX/.claude/dev-routes.md" 2>/dev/null | awk -F: '{s+=$NF} END{print s+0}')"
assert_gt 0 "$n_full_honcho" "honcho references present in vec-memory-variant policy"
grep -q 'variant: vec-memory' "$SANDBOX/.claude/CLAUDE.md" && pass "header records variant: vec-memory" || fail "no variant in header"

# ---- Scenario 8: re-emit + variant swap on --enable-group ---------------
announce "Scenario 8: policy swaps variant when vec-memory is enabled"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > /dev/null 2>&1
ts1="$(head -1 "$SANDBOX/.claude/CLAUDE.md")"
sleep 1
HOME="$SANDBOX" bash "$INSTALL" --yes --enable-group vec-memory > /dev/null 2>&1
ts2="$(head -1 "$SANDBOX/.claude/CLAUDE.md")"
if [[ "$ts1" != "$ts2" ]]; then pass "policy header changed (variant/timestamp)"; else fail "header unchanged"; fi
n_after="$(grep -c 'honcho-recall\|honcho-remember\|honcho-manage' "$SANDBOX/.claude/CLAUDE.md" "$SANDBOX/.claude/dev-routes.md" 2>/dev/null | awk -F: '{s+=$NF} END{print s+0}')"
assert_gt 0 "$n_after" "honcho refs re-appeared after variant swap"
grep -q 'variant: vec-memory' "$SANDBOX/.claude/CLAUDE.md" && pass "header now reports variant: vec-memory" || fail "variant did not swap"

# ---- Scenario 9: policy conflict without header ---------------------------
announce "Scenario 9: policy conflict on foreign CLAUDE.md"
SANDBOX="$(mktemp -d)"
mkdir -p "$SANDBOX/.claude"
echo "# user's own CLAUDE.md" > "$SANDBOX/.claude/CLAUDE.md"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > "$SANDBOX/out" 2>&1
rc=$?
if (( rc != 0 )); then pass "foreign policy conflict returns non-zero (rc=$rc)"; else fail "returned 0"; fi
grep -q "user's own" "$SANDBOX/.claude/CLAUDE.md" && pass "foreign CLAUDE.md untouched" || fail "foreign CLAUDE.md modified"
# now with --force
HOME="$SANDBOX" bash "$INSTALL" --yes --force --wired claude --groups core > /dev/null 2>&1
rc=$?
assert_eq 0 "$rc" "force resolves conflict"
ls "$SANDBOX/.claude/" | grep -q '.tacit-backup' && pass "backup file created" || fail "no .tacit-backup file"

# ---- Scenario 10: release.sh --dry-run ------------------------------------
announce "Scenario 10: release.sh dry-run"
out="$(bash "$RELEASE" --dry-run --force patch 2>&1)"
rc=$?
assert_eq 0 "$rc" "release --dry-run exits 0"
if [[ "$out" == *"v0.1.0"* ]] || [[ "$out" == *"new:"* ]]; then
    pass "release proposes a version"
else
    fail "release output missing version proposal"
fi

# ---- Scenario 11: legacy 'honcho' group name migrates to vec-memory ----
announce "Scenario 11: legacy honcho group name is aliased to vec-memory"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core,honcho > "$SANDBOX/out" 2>&1
rc=$?
assert_eq 0 "$rc" "install with --groups core,honcho exits 0"
grep -qE '^\s*-\s+vec-memory\s*$' "$SANDBOX/.config/tacit-skills/installer.yaml" \
    && pass "config recorded as vec-memory" \
    || fail "config still records honcho"
n_honcho="$(find "$SANDBOX/.claude/skills" -maxdepth 1 -type l -name 'honcho-*' 2>/dev/null | wc -l)"
assert_eq "$HONCHO_N" "$n_honcho" "honcho skills installed via legacy alias"
grep -q 'variant: vec-memory' "$SANDBOX/.claude/CLAUDE.md" && pass "vec-memory variant picked" || fail "wrong variant"

# ---- Scenario 14: --check on fresh install is clean -----------------------
announce "Scenario 14: --check after fresh install"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > /dev/null 2>&1
HOME="$SANDBOX" bash "$INSTALL" --check > "$SANDBOX/check.out" 2>&1
rc=$?
assert_eq 0 "$rc" "--check reports in sync (rc=0)"
grep -q "in sync" "$SANDBOX/check.out" && pass "--check output says 'in sync'" || fail "no 'in sync' in output"

# ---- Scenario 15: --check detects skill-set drift -------------------------
announce "Scenario 15: --check flags missing symlink as drift"
rm -f "$SANDBOX/.claude/skills/pivot"
HOME="$SANDBOX" bash "$INSTALL" --check > "$SANDBOX/check2.out" 2>&1
rc=$?
if (( rc != 0 )); then pass "--check returns non-zero on drift (rc=$rc)"; else fail "returned 0"; fi
grep -q "skill-set drift" "$SANDBOX/check2.out" && pass "reports skill-set drift" || fail "no drift message"

# ---- Scenario 16: --check ignores dev-build sha drift in symlink mode ----
announce "Scenario 16: --check ignores dev-build sha in symlink mode"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > /dev/null 2>&1
# Fake an older sha in the config; symlink mode should not report version drift.
sed -i 's/^version: .*/version: v0.0.0-deadbee/' "$SANDBOX/.config/tacit-skills/installer.yaml"
HOME="$SANDBOX" bash "$INSTALL" --check > "$SANDBOX/check3.out" 2>&1
rc=$?
assert_eq 0 "$rc" "--check ignores dev-build sha (symlink)"
if grep -q "version drift" "$SANDBOX/check3.out"; then fail "reported version drift in symlink mode"; else pass "no spurious version-drift message"; fi

# ---- Scenario 17: agent wrappers install core-only ------------------------
announce "Scenario 17: agent wrappers install (core-only)"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > "$SANDBOX/out" 2>&1
rc=$?
assert_eq 0 "$rc" "install exits 0"
n_agents="$(find "$SANDBOX/.claude/agents" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l)"
assert_eq "$CORE_AGENTS_N" "$n_agents" "core agent wrappers written"
# every one carries the tacit marker
n_marked=0
if (( CORE_AGENTS_N > 0 )); then
    for f in "$SANDBOX/.claude/agents"/*.md; do
        head -n 20 "$f" 2>/dev/null | grep -q "^<!-- tacit-skills agent v1" && n_marked=$((n_marked+1))
    done
fi
assert_eq "$CORE_AGENTS_N" "$n_marked" "agent files carry marker"
# frontmatter is intact (must begin with ---)
if (( CORE_AGENTS_N > 0 )); then
    first_agent="$(ls "$SANDBOX/.claude/agents"/*.md | head -1)"
    if [[ "$(head -1 "$first_agent")" == "---" ]]; then pass "frontmatter preserved (--- first)"; else fail "first line not ---"; fi
fi

# ---- Scenario 18: uninstall removes agent wrappers and dir ---------------
announce "Scenario 18: uninstall-vendor removes agents"
HOME="$SANDBOX" bash "$INSTALL" --uninstall-vendor claude > "$SANDBOX/uninstall.out" 2>&1
rc=$?
assert_eq 0 "$rc" "uninstall exits 0"
[[ ! -e "$SANDBOX/.claude/agents" ]] && pass "agents dir removed" || fail "agents dir still present"

# ---- Scenario 19: --no-agents skips agent install ------------------------
announce "Scenario 19: --no-agents skips agents"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --no-agents --wired claude --groups core > "$SANDBOX/out" 2>&1
rc=$?
assert_eq 0 "$rc" "install exits 0"
[[ ! -e "$SANDBOX/.claude/agents" ]] && pass "no agents dir created" || fail "agents dir created despite --no-agents"

# ---- Scenario 20: agent group filter (core-only excludes honcho-*) -------
announce "Scenario 20: agent group filter — core-only excludes honcho-*"
SANDBOX="$(mktemp -d)"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > /dev/null 2>&1
n_honcho_agents=0
if [[ -d "$SANDBOX/.claude/agents" ]]; then
    n_honcho_agents="$(find "$SANDBOX/.claude/agents" -maxdepth 1 -type f -name 'honcho-*.md' | wc -l)"
fi
assert_eq 0 "$n_honcho_agents" "no honcho-* agents in core-only"

# ---- Scenario 21: enable-group vec-memory pulls honcho agents -----------
announce "Scenario 21: --enable-group vec-memory pulls honcho agents (if any)"
HOME="$SANDBOX" bash "$INSTALL" --yes --enable-group vec-memory > /dev/null 2>&1
n_honcho_agents2=0
if [[ -d "$SANDBOX/.claude/agents" ]]; then
    n_honcho_agents2="$(find "$SANDBOX/.claude/agents" -maxdepth 1 -type f -name 'honcho-*.md' | wc -l)"
fi
assert_eq "$HONCHO_AGENTS_N" "$n_honcho_agents2" "honcho agents present after enable"

# ---- Scenario 22: agent conflict on foreign file --------------------------
announce "Scenario 22: agent conflict on foreign wrapper"
SANDBOX="$(mktemp -d)"
mkdir -p "$SANDBOX/.claude/agents"
# Use the first core agent name to guarantee overlap.
first_core_agent="$(ls "$REPO_ROOT/.agents"/*.md 2>/dev/null | while read -r f; do
    n="$(basename "$f" .md)"
    [[ "$n" == honcho-* ]] || { printf '%s\n' "$n"; break; }
done)"
if [[ -z "$first_core_agent" ]]; then
    pass "no core agents in .agents/ — scenario N/A"
else
    printf -- '---\nname: %s\ndescription: user override\n---\nuser content\n' "$first_core_agent" > "$SANDBOX/.claude/agents/$first_core_agent.md"
    HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core > "$SANDBOX/out" 2>&1
    rc=$?
    if (( rc != 0 )); then pass "foreign agent conflict returns non-zero (rc=$rc)"; else fail "returned 0"; fi
    grep -q "user content" "$SANDBOX/.claude/agents/$first_core_agent.md" && pass "foreign agent untouched" || fail "foreign agent modified"
    # now with --force
    HOME="$SANDBOX" bash "$INSTALL" --yes --force --wired claude --groups core > /dev/null 2>&1
    rc=$?
    assert_eq 0 "$rc" "force resolves agent conflict"
    ls "$SANDBOX/.claude/agents/" | grep -q '.tacit-backup' && pass "agent backup created" || fail "no agent backup"
fi

# ---- Scenario 23: --agents-dir sends wrappers to a custom path ------------
announce "Scenario 23: --agents-dir override"
SANDBOX="$(mktemp -d)"
CUSTOM_AGENTS="$SANDBOX/somewhere-else/agents"
HOME="$SANDBOX" bash "$INSTALL" --yes --wired claude --groups core \
    --agents-dir "claude=$CUSTOM_AGENTS" > "$SANDBOX/out" 2>&1
rc=$?
assert_eq 0 "$rc" "install exits 0 with custom agents_dir"
n_custom="$(find "$CUSTOM_AGENTS" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l)"
assert_eq "$CORE_AGENTS_N" "$n_custom" "agents written to custom dir"
[[ ! -e "$SANDBOX/.claude/agents" ]] && pass "no agents at default path" || fail "agents also at default path"
# Config should record the custom path so reruns hit it.
grep -q "agents_dir: $CUSTOM_AGENTS" "$SANDBOX/.config/tacit-skills/installer.yaml" \
    && pass "agents_dir recorded in installer.yaml" \
    || fail "agents_dir missing from installer.yaml"
# Rerun should be idempotent (no new files, no conflict).
HOME="$SANDBOX" bash "$INSTALL" --yes > "$SANDBOX/out2" 2>&1
rc=$?
assert_eq 0 "$rc" "rerun exits 0"
n_after="$(find "$CUSTOM_AGENTS" -maxdepth 1 -type f -name '*.md' 2>/dev/null | wc -l)"
assert_eq "$CORE_AGENTS_N" "$n_after" "rerun leaves same agent count"

# ---- summary --------------------------------------------------------------
printf '\n========================================\n'
printf 'PASS: %d  FAIL: %d\n' "$pass_count" "$fail_count"
if (( fail_count > 0 )); then exit 1; fi
exit 0
