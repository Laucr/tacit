#!/usr/bin/env bash
# collect_metrics.sh — run tokei on a directory and output structured JSON + markdown table
# Usage: bash collect_metrics.sh [target_directory] [--scope subpath]
# Output: JSON to stdout (pipe-friendly), markdown table to stderr (for report embedding)
set -euo pipefail

TARGET_DIR="${1:-.}"
SCOPE=""

# Parse --scope flag
shift || true
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)
      SCOPE="$2"
      shift 2
      ;;
    *)
      shift
      ;;
  esac
done

# Apply scope if provided
if [ -n "$SCOPE" ]; then
  SCAN_DIR="$TARGET_DIR/$SCOPE"
else
  SCAN_DIR="$TARGET_DIR"
fi

if [ ! -d "$SCAN_DIR" ]; then
  echo "{\"error\": \"Directory not found: $SCAN_DIR\"}" >&1
  exit 1
fi

# Check tokei is available
if ! command -v tokei &>/dev/null; then
  echo "{\"error\": \"tokei not installed. Run check_prerequisites.sh first.\"}" >&1
  exit 1
fi

# --- Run tokei ---

TOKEI_JSON=$(tokei "$SCAN_DIR" --output json 2>/dev/null)

if [ -z "$TOKEI_JSON" ]; then
  echo "{\"error\": \"tokei produced no output for $SCAN_DIR\"}" >&1
  exit 1
fi

# --- Parse with built-in tools (no jq dependency) ---
# We use node if available, otherwise provide raw tokei output

if command -v node &>/dev/null; then
  # Use node to parse and restructure the tokei JSON
  node -e "
    const data = JSON.parse(process.argv[1]);
    const languages = [];
    let totalFiles = 0, totalCode = 0, totalComments = 0, totalBlanks = 0;

    for (const [lang, info] of Object.entries(data)) {
      // Skip inner keys and Total
      if (lang === 'Total' || !info || typeof info !== 'object') continue;
      if (!info.code && info.code !== 0) continue;

      const files = (info.reports || info.children || []).length || info.inaccurate || 0;
      // tokei v12+ uses 'code', 'comments', 'blanks' at top level per language
      const code = info.code || 0;
      const comments = info.comments || 0;
      const blanks = info.blanks || 0;

      languages.push({ name: lang, files: files, code, comments, blanks });
      totalFiles += files;
      totalCode += code;
      totalComments += comments;
      totalBlanks += blanks;
    }

    // Sort by code lines descending
    languages.sort((a, b) => b.code - a.code);

    const result = {
      scan_directory: '$SCAN_DIR',
      total_files: totalFiles,
      total_code: totalCode,
      total_comments: totalComments,
      total_blanks: totalBlanks,
      total_lines: totalCode + totalComments + totalBlanks,
      languages: languages
    };

    // JSON to stdout
    console.log(JSON.stringify(result, null, 2));

    // Markdown table to stderr
    const lines = [
      '| Language | Files | Code | Comments | Blanks |',
      '|----------|------:|-----:|---------:|-------:|'
    ];
    for (const l of languages) {
      lines.push('| ' + l.name + ' | ' + l.files + ' | ' + l.code + ' | ' + l.comments + ' | ' + l.blanks + ' |');
    }
    lines.push('| **Total** | **' + totalFiles + '** | **' + totalCode + '** | **' + totalComments + '** | **' + totalBlanks + '** |');
    process.stderr.write(lines.join('\n') + '\n');
  " "$TOKEI_JSON"
else
  # Fallback: output raw tokei JSON and run tokei again for human-readable table
  echo "$TOKEI_JSON"
  echo "" >&2
  echo "--- tokei summary (install node for structured output) ---" >&2
  tokei "$SCAN_DIR" >&2
fi
