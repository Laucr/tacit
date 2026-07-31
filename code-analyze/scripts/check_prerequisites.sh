#!/usr/bin/env bash
# check_prerequisites.sh — validate that required tools are available for code-analyze
# Usage: bash check_prerequisites.sh [target_directory]
# Output: JSON to stdout with tool availability and detected stack
# Exit 0 = all required tools present, exit 1 = missing tools
set -euo pipefail

TARGET_DIR="${1:-.}"
MISSING=()
DETECTED_STACK="generic"

# --- Tool checks ---

# tokei (required)
if command -v tokei &>/dev/null; then
  TOKEI_VERSION=$(tokei --version 2>/dev/null | head -1)
  TOKEI_OK=true
else
  TOKEI_OK=false
  MISSING+=("tokei")
fi

# go (conditional — only required if Go files exist)
GO_OK=false
GO_REQUIRED=false
if find "$TARGET_DIR" -maxdepth 3 -name '*.go' -print -quit 2>/dev/null | grep -q .; then
  GO_REQUIRED=true
  if command -v go &>/dev/null; then
    GO_OK=true
    GO_VERSION=$(go version 2>/dev/null | awk '{print $3}')
  else
    MISSING+=("go")
  fi
fi

# node (optional — for potential future scripts)
if command -v node &>/dev/null; then
  NODE_OK=true
else
  NODE_OK=false
fi

# --- Stack detection ---

if [ "$GO_REQUIRED" = true ]; then
  DETECTED_STACK="go"
fi

# --- Build JSON output ---

# Helper: array to JSON array string
json_array() {
  local result="["
  local first=true
  for item in "$@"; do
    if [ "$first" = true ]; then
      first=false
    else
      result+=","
    fi
    result+="\"$item\""
  done
  result+="]"
  echo "$result"
}

OK=true
if [ ${#MISSING[@]} -gt 0 ]; then
  OK=false
fi

MISSING_JSON=$(json_array "${MISSING[@]+"${MISSING[@]}"}")

cat <<EOF
{
  "ok": $OK,
  "missing": $MISSING_JSON,
  "detected_stack": "$DETECTED_STACK",
  "tools": {
    "tokei": $TOKEI_OK,
    "go": $GO_OK,
    "go_required": $GO_REQUIRED,
    "node": $NODE_OK
  }
}
EOF

# --- User-friendly install hints on failure ---

if [ "$OK" = false ]; then
  echo "" >&2
  echo "Missing required tools:" >&2
  for tool in "${MISSING[@]}"; do
    case "$tool" in
      tokei)
        echo "  tokei — Install via:" >&2
        echo "    cargo install tokei      (Rust toolchain)" >&2
        echo "    brew install tokei       (macOS Homebrew)" >&2
        echo "    apt install tokei        (Debian/Ubuntu, if available)" >&2
        echo "    Or download from: https://github.com/XAMPPRocky/tokei/releases" >&2
        ;;
      go)
        echo "  go — Install from: https://go.dev/dl/" >&2
        ;;
    esac
  done
  exit 1
fi

exit 0
