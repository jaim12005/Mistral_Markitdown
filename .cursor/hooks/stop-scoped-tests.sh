#!/usr/bin/env bash
# .cursor/hooks/stop-scoped-tests.sh
# Runs pytest scoped to changed files at end of agent run.
# Returns followup_message on failure so the agent can attempt a fix (up to loop_limit).

set -euo pipefail

RESULTS_FILE=$(mktemp /tmp/cursor-test-results-XXXXXX.txt)
FAILED=0

# Get changed files (staged + unstaged)
CHANGED_FILES=$(git diff --name-only HEAD 2>/dev/null || git diff --name-only 2>/dev/null || echo "")

if [ -z "$CHANGED_FILES" ]; then
  echo '{}'
  exit 0
fi

# --- Python ---
PY_FILES=$(echo "$CHANGED_FILES" | grep -E '\.py$' || true)
if [ -n "$PY_FILES" ]; then
  # Find test files related to changed source files
  PY_TEST_FILES=""
  for f in $PY_FILES; do
    dirname=$(dirname "$f")
    basename=$(basename "$f" .py)
    # Check common test locations matching this project's structure
    for candidate in \
      "tests/test_${basename}.py" \
      "tests/${dirname}/test_${basename}.py"; do
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
    # Deduplicate
    PY_TEST_FILES=$(echo "$PY_TEST_FILES" | tr ' ' '\n' | sort -u | tr '\n' ' ')
    python3 -m pytest -q --no-header --tb=short $PY_TEST_FILES >> "$RESULTS_FILE" 2>&1 || FAILED=1
  fi
fi

# --- Report ---
if [ "$FAILED" -eq 1 ]; then
  # Truncate to last 80 lines to keep followup reasonable
  TAIL=$(tail -80 "$RESULTS_FILE")
  cat <<EOF
{"followup_message":"Tests failed for changed files. Results written to ${RESULTS_FILE}. Last lines:\n\n${TAIL}\n\nFix the failures and re-run."}
EOF
  exit 0
fi

# All passed or nothing to run
echo '{}'
exit 0
