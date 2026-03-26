#!/usr/bin/env bash
# .cursor/hooks/after-file-format.sh
# Runs black + isort after agent edits to .py files.
# Note: does NOT fire on "Accept All" -- pair with editor format-on-save for final state.

set -euo pipefail

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.file_edit.path // empty')

if [ -z "$FILE" ] || [ ! -f "$FILE" ]; then
  exit 0
fi

EXT="${FILE##*.}"

case "$EXT" in
  py)
    if command -v black &>/dev/null; then
      black --quiet --line-length 120 "$FILE" 2>/dev/null || true
    fi
    if command -v isort &>/dev/null; then
      isort --profile black --line-length 120 "$FILE" 2>/dev/null || true
    fi
    ;;
esac

exit 0
