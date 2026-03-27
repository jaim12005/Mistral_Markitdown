#!/usr/bin/env bash
# .cursor/hooks/after-file-format.sh
# Runs the appropriate formatter after agent file edits.
# Note: does NOT fire on "Accept All" -- pair with editor format-on-save for final state.

set -euo pipefail

# Resolve python — Windows often only has "python", not "python3"
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
if [ -z "$PY" ]; then
  exit 0
fi

INPUT=$(cat)

FILE=$(echo "$INPUT" | "$PY" -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('file_edit', {}).get('path', ''))
except: pass
" 2>/dev/null || echo "")

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  exit 0
fi

EXT="${FILE##*.}"

case "$EXT" in
  js|jsx|ts|tsx|json|css|scss|html|md|yaml|yml)
    if command -v npx &>/dev/null && [ -f "node_modules/.bin/prettier" ]; then
      npx prettier --write "$FILE" 2>/dev/null || true
    fi
    ;;
  py)
    if command -v ruff &>/dev/null; then
      ruff format "$FILE" 2>/dev/null || true
      ruff check --fix "$FILE" 2>/dev/null || true
    elif command -v black &>/dev/null; then
      black --quiet "$FILE" 2>/dev/null || true
    fi
    ;;
  tf|tfvars)
    if command -v terraform &>/dev/null; then
      terraform fmt "$FILE" 2>/dev/null || true
    fi
    ;;
  go)
    if command -v gofmt &>/dev/null; then
      gofmt -w "$FILE" 2>/dev/null || true
    fi
    ;;
  rs)
    if command -v rustfmt &>/dev/null; then
      rustfmt "$FILE" 2>/dev/null || true
    fi
    ;;
esac

exit 0
