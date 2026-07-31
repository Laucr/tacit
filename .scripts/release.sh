#!/usr/bin/env bash
# tacit-skills / release.sh
#
# Cut a new release by tagging HEAD with an annotated semver tag. Feeds the
# installer's version-check (install.sh compares config `version:` against
# `git describe`). Idempotent: refuses to overwrite an existing tag unless
# --force is passed.
#
# Usage:
#   bash .scripts/release.sh patch                 # v0.3.0 -> v0.3.1
#   bash .scripts/release.sh minor -m "add x-skill"
#   bash .scripts/release.sh major
#   bash .scripts/release.sh v1.2.3                # explicit version
#   bash .scripts/release.sh --dry-run patch       # preview only
#   bash .scripts/release.sh --push patch          # tag + push to origin
#
# Preflight (each bypassable with --force):
#   - working tree must be clean
#   - HEAD must not already carry a tag
#
# By design:
#   - No CHANGELOG.md maintenance; the annotated tag carries `git log --oneline`.
#   - --push is opt-in. A mistaken local tag is `git tag -d`; a pushed tag needs
#     coordination.

set -euo pipefail
IFS=$'\n\t'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SCRIPT_DIR/.." rev-parse --show-toplevel 2>/dev/null || true)"

die()  { printf 'release: %s\n' "$*" >&2; exit 1; }
warn() { printf 'release: warn: %s\n' "$*" >&2; }
info() { printf 'release: %s\n' "$*"; }

usage() {
    sed -n '2,26p' "$0" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# ---- args ------------------------------------------------------------------

BUMP=""
MESSAGE=""
DRY_RUN=0
PUSH=0
FORCE=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        major|minor|patch)
            [[ -n "$BUMP" ]] && die "multiple version args"
            BUMP="$1"; shift ;;
        v[0-9]*)
            [[ -n "$BUMP" ]] && die "multiple version args"
            BUMP="$1"; shift ;;
        -m|--message)
            [[ $# -lt 2 ]] && die "$1 requires an argument"
            MESSAGE="$2"; shift 2 ;;
        --dry-run) DRY_RUN=1; shift ;;
        --push)    PUSH=1; shift ;;
        --force)   FORCE=1; shift ;;
        -h|--help) usage 0 ;;
        *)         die "unknown arg: $1  (try --help)" ;;
    esac
done

[[ -z "$BUMP" ]] && die "specify major|minor|patch|vX.Y.Z (see --help)"
[[ -z "$REPO_ROOT" ]] && die "not in a git repository"

# ---- preflight -------------------------------------------------------------

if ! git -C "$REPO_ROOT" diff-index --quiet HEAD -- 2>/dev/null; then
    if (( FORCE )); then
        warn "working tree is dirty (--force allows it)"
    else
        die "working tree is dirty; commit or stash first (--force to bypass)"
    fi
fi

if head_tag="$(git -C "$REPO_ROOT" describe --tags --exact-match HEAD 2>/dev/null)"; then
    if (( FORCE )); then
        warn "HEAD is already tagged as $head_tag (--force allows a new tag on top)"
    else
        die "HEAD is already tagged as $head_tag (--force to add another)"
    fi
fi

# ---- current version -------------------------------------------------------

CURRENT="$(git -C "$REPO_ROOT" describe --tags --abbrev=0 2>/dev/null || true)"

# ---- compute new version ---------------------------------------------------

parse_semver() {
    # emits three numbers on stdout, one per line
    local v="$1"
    [[ "$v" =~ ^v?([0-9]+)\.([0-9]+)\.([0-9]+)$ ]] || return 1
    printf '%s\n%s\n%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
}

case "$BUMP" in
    major|minor|patch)
        if [[ -z "$CURRENT" ]]; then
            # No tags yet — seed at v0.1.0 regardless of bump.
            NEW="v0.1.0"
            info "no existing tags; proposing initial release $NEW"
        else
            if ! parts=($(parse_semver "$CURRENT")); then
                die "cannot parse current tag '$CURRENT' as vX.Y.Z"
            fi
            major="${parts[0]}"; minor="${parts[1]}"; patch="${parts[2]}"
            case "$BUMP" in
                major) major=$((major+1)); minor=0; patch=0 ;;
                minor) minor=$((minor+1)); patch=0 ;;
                patch) patch=$((patch+1)) ;;
            esac
            NEW="v${major}.${minor}.${patch}"
        fi
        ;;
    v*)
        # Explicit version.
        if ! parse_semver "$BUMP" > /dev/null; then
            die "explicit version must match vMAJOR.MINOR.PATCH (got: $BUMP)"
        fi
        NEW="$BUMP"
        ;;
esac

# Reject moving/duplicating an existing tag.
if git -C "$REPO_ROOT" rev-parse --verify "refs/tags/$NEW" >/dev/null 2>&1; then
    if (( FORCE )); then
        warn "$NEW already exists; --force will refuse anyway (use git tag -d first)"
        die "$NEW already exists as a tag"
    else
        die "$NEW already exists as a tag (delete it first if that's intentional)"
    fi
fi

# ---- build message ---------------------------------------------------------

if [[ -z "$MESSAGE" ]]; then
    MESSAGE="Release $NEW"
    if [[ -n "$CURRENT" ]]; then
        shortlog="$(git -C "$REPO_ROOT" log --oneline "$CURRENT..HEAD" 2>/dev/null || true)"
    else
        shortlog="$(git -C "$REPO_ROOT" log --oneline 2>/dev/null | head -50 || true)"
    fi
    if [[ -n "$shortlog" ]]; then
        MESSAGE="$MESSAGE"$'\n\n'"$shortlog"
    fi
fi

# ---- report ----------------------------------------------------------------

info "current: ${CURRENT:-<none>}"
info "new:     $NEW"
info "message:"
printf '  |  %s\n' "$MESSAGE" | sed 's/$/ /'

# ---- execute ---------------------------------------------------------------

TAG_CMD=(git -C "$REPO_ROOT" tag -a "$NEW" -m "$MESSAGE")
PUSH_CMD=(git -C "$REPO_ROOT" push origin "$NEW")

if (( DRY_RUN )); then
    info "DRY-RUN — would execute:"
    printf '  %q ' "${TAG_CMD[@]}"; printf '\n'
    if (( PUSH )); then
        printf '  %q ' "${PUSH_CMD[@]}"; printf '\n'
    fi
    exit 0
fi

"${TAG_CMD[@]}"
info "tagged $NEW"

if (( PUSH )); then
    "${PUSH_CMD[@]}"
    info "pushed $NEW to origin"
else
    info "not pushed. Push with:  git push origin $NEW"
fi
