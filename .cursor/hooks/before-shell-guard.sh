#!/usr/bin/env bash
# .cursor/hooks/before-shell-guard.sh
# Blocks destructive shell commands. Exit 0 + JSON = allow/deny decision.
# Exit 2 = hard block. failClosed: true in hooks.json means any other error also blocks.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.shell_execution.command // empty')

if [ -z "$COMMAND" ]; then
  echo '{"permission":"allow"}'
  exit 0
fi

# Normalize for matching
CMD_LOWER=$(echo "$COMMAND" | tr '[:upper:]' '[:lower:]')

# --- Destructive filesystem ---
if echo "$CMD_LOWER" | grep -qE '(^|\s|;|&&|\|\|)rm\s+(-[a-z]*f[a-z]*\s+)?-[a-z]*r|rm\s+-rf\b'; then
  echo '{"permission":"deny","agent_message":"Blocked: recursive rm. Run manually if intended."}'
  exit 0
fi

if echo "$CMD_LOWER" | grep -qE 'find\s.*-delete'; then
  echo '{"permission":"deny","agent_message":"Blocked: find -delete. Run manually if intended."}'
  exit 0
fi

if echo "$CMD_LOWER" | grep -qE 'mkfs\b|dd\s.*of=/dev/'; then
  echo '{"permission":"deny","agent_message":"Blocked: disk-level write operation."}'
  exit 0
fi

# --- Git force/destructive ---
if echo "$CMD_LOWER" | grep -qE 'git\s+push\s.*--force|git\s+push\s.*-f\b|git\s+push\s.*--delete'; then
  echo '{"permission":"deny","agent_message":"Blocked: force push or branch delete. Run manually if intended."}'
  exit 0
fi

if echo "$CMD_LOWER" | grep -qE 'git\s+reset\s+--hard|git\s+clean\s+-[a-z]*f'; then
  echo '{"permission":"deny","agent_message":"Blocked: git reset --hard or git clean -f. Run manually if intended."}'
  exit 0
fi

if echo "$CMD_LOWER" | grep -qE 'git\s+checkout\s+-f\b'; then
  echo '{"permission":"deny","agent_message":"Blocked: git checkout -f. Run manually if intended."}'
  exit 0
fi

# --- System ---
if echo "$CMD_LOWER" | grep -qE '(^|\s|;)(reboot|shutdown|halt|poweroff)\b'; then
  echo '{"permission":"deny","agent_message":"Blocked: system power command."}'
  exit 0
fi

# Default: allow
echo '{"permission":"allow"}'
exit 0
