#!/usr/bin/env bash
# .cursor/hooks/subagent-gate.sh
# Controls which subagents are allowed to spawn.
# subagentStart only supports allow/deny (ask is treated as deny).
# Edit ALLOWED_TYPES and ALLOWED_CUSTOM to match your setup.

set -euo pipefail

# Resolve python — Windows often only has "python", not "python3"
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
if [ -z "$PY" ]; then
  echo '{"permission":"allow"}'
  exit 0
fi

INPUT=$(cat)

eval "$( echo "$INPUT" | "$PY" -c "
import sys, json
try:
    d = json.load(sys.stdin)
    sa = d.get('subagent_start', {})
    print('SUBAGENT_TYPE=' + repr(sa.get('subagent_type', '')))
    print('SUBAGENT_ID=' + repr(sa.get('subagent_id', '')))
except:
    print('SUBAGENT_TYPE=')
    print('SUBAGENT_ID=')
" 2>/dev/null )"

# --- Built-in subagent types: allow by default ---
# Known built-ins: explore, bash, browser
# Remove any you want to block (e.g., remove "browser" to prevent web access)
ALLOWED_BUILTINS=(
  "explore"
  "bash"
  "browser"
)

# --- Custom subagent names: allowlist ---
# Add the names of your .cursor/agents/*.md subagents here
ALLOWED_CUSTOM=(
  "verifier"
  "test-runner"
  "researcher"
)

# Check built-ins
for allowed in "${ALLOWED_BUILTINS[@]}"; do
  if [ "$SUBAGENT_TYPE" = "$allowed" ]; then
    echo '{"permission":"allow"}'
    exit 0
  fi
done

# Check custom subagents
for allowed in "${ALLOWED_CUSTOM[@]}"; do
  if [ "$SUBAGENT_TYPE" = "$allowed" ] || [ "$SUBAGENT_ID" = "$allowed" ]; then
    echo '{"permission":"allow"}'
    exit 0
  fi
done

# If the type is empty or unrecognized but looks like a built-in task delegation, allow
# (Cursor sometimes uses internal subagent types not exposed in docs)
if [ -z "$SUBAGENT_TYPE" ]; then
  echo '{"permission":"allow"}'
  exit 0
fi

# --- Deny unrecognized subagent types ---
echo "{\"permission\":\"deny\",\"agent_message\":\"Blocked subagent type: ${SUBAGENT_TYPE}. Not on the project allowlist. Add to .cursor/hooks/subagent-gate.sh if safe.\"}"
exit 0
