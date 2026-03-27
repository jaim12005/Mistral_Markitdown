#!/usr/bin/env bash
# .cursor/hooks/stop-scoped-tests.sh
# Runs tests scoped to changed files at end of agent run.
# Returns followup_message on failure so the agent can attempt a fix (up to loop_limit).
# Output is written to a temp file to avoid bloating agent context.

set -euo pipefail

# Resolve python — Windows often only has "python", not "python3"
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
if [ -z "$PY" ]; then
  echo '{}'
  exit 0
fi

# Cross-platform mktemp — /tmp/ doesn't exist on Windows
RESULTS_FILE=$(mktemp /tmp/cursor-test-results-XXXXXX.txt 2>/dev/null || mktemp)
FAILED=0

# Get changed files (staged + unstaged)
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only 2>/dev/null || echo "")

if [ -z "$CHANGED_FILES" ]; then
  echo '{}'
  exit 0
fi

# --- JavaScript / TypeScript ---
JS_FILES=$(echo "$CHANGED_FILES" | grep -E '\.(js|jsx|ts|tsx)$' || true)
if [ -n "$JS_FILES" ]; then
  if [ -f "node_modules/.bin/vitest" ]; then
    npx vitest related --run $JS_FILES > "$RESULTS_FILE" 2>&1 || FAILED=1
  elif [ -f "node_modules/.bin/jest" ]; then
    npx jest --findRelatedTests $JS_FILES > "$RESULTS_FILE" 2>&1 || FAILED=1
  fi
fi

# --- Python ---
PY_FILES=$(echo "$CHANGED_FILES" | grep -E '\.py$' || true)
if [ -n "$PY_FILES" ]; then
  # Find test files related to changed source files
  PY_TEST_FILES=""
  for f in $PY_FILES; do
    dir=$(dirname "$f")
    base=$(basename "$f" .py)
    # Check common test locations
    for candidate in \
      "${dir}/test_${base}.py" \
      "${dir}/tests/test_${base}.py" \
      "tests/test_${base}.py" \
      "tests/${dir}/test_${base}.py"; do
      if [ -f "$candidate" ]; then
        PY_TEST_FILES="$PY_TEST_FILES $candidate"
      fi
    done
    # Also include changed test files directly
    if echo "$f" | grep -qE '(^|/)test_.*\.py$'; then
      PY_TEST_FILES="$PY_TEST_FILES $f"
    fi
  done

  if [ -n "$PY_TEST_FILES" ]; then
    if command -v pytest &>/dev/null; then
      pytest -q $PY_TEST_FILES >> "$RESULTS_FILE" 2>&1 || FAILED=1
    elif "$PY" -m pytest --version &>/dev/null; then
      "$PY" -m pytest -q $PY_TEST_FILES >> "$RESULTS_FILE" 2>&1 || FAILED=1
    fi
  fi
fi

# --- Go ---
GO_FILES=$(echo "$CHANGED_FILES" | grep -E '\.go$' || true)
if [ -n "$GO_FILES" ]; then
  if command -v go &>/dev/null; then
    GO_DIRS=$(echo "$GO_FILES" | while read -r f; do dirname "$f"; done | sort -u | sed 's|^|./|')
    go test $GO_DIRS >> "$RESULTS_FILE" 2>&1 || FAILED=1
  fi
fi

# --- Report ---
if [ "$FAILED" -eq 1 ]; then
  # Build JSON response safely via python (proper escaping, no heredoc issues)
  TAIL=$(tail -80 "$RESULTS_FILE")
  "$PY" -c "
import json, sys
tail = sys.stdin.read()
msg = 'Tests failed for changed files. Last lines:\n\n' + tail + '\n\nFix the failures and re-run.'
print(json.dumps({'followup_message': msg}))
" <<< "$TAIL"
  exit 0
fi

# All passed or nothing to run
echo '{}'
exit 0
