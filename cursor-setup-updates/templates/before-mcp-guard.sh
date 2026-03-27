#!/usr/bin/env bash
# .cursor/hooks/before-mcp-guard.sh
# Defaults to deny for MCP tools not on the allowlist.
# Designed around deny because hook-side "ask" is not reliably enforced in current builds.
# Edit ALLOWED_TOOLS to match your actual MCP server/tool surface.

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
    mcp = d.get('mcp_execution', {})
    print('SERVER=' + repr(mcp.get('server_name', '')))
    print('TOOL=' + repr(mcp.get('tool_name', '')))
except:
    print('SERVER=')
    print('TOOL=')
" 2>/dev/null )"

if [ -z "$SERVER" ] || [ -z "$TOOL" ]; then
  echo '{"permission":"allow"}'
  exit 0
fi

# --- Read-only tools: always allow ---
# Add your read-only tool names here (server:tool format)
ALLOWED_TOOLS=(
  # Tracker / project management (read)
  "linear:getIssue"
  "linear:listIssues"
  "linear:searchIssues"
  "jira:getIssue"
  "jira:searchIssues"
  # Docs (read)
  "internal-docs:search"
  "internal-docs:getDocument"
  # Database (read-only queries)
  "readonly-db:query"
  "readonly-db:describeTable"
  "readonly-db:listTables"
)

FULL_KEY="${SERVER}:${TOOL}"

for allowed in "${ALLOWED_TOOLS[@]}"; do
  if [ "$FULL_KEY" = "$allowed" ]; then
    echo '{"permission":"allow"}'
    exit 0
  fi
done

# --- Everything else: deny by default ---
echo "{\"permission\":\"deny\",\"agent_message\":\"Blocked MCP tool: ${SERVER}:${TOOL}. Not on the project allowlist. Run manually or add to .cursor/hooks/before-mcp-guard.sh if safe.\"}"
exit 0
