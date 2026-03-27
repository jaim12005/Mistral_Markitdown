# Cursor Setup Skill — Cross-Platform Fixes

Changes based on real-world issues encountered deploying on Windows + macOS/Linux.

## How to apply

Copy the contents of this `cursor-setup-updates/` folder over your skill:

```bash
# From your Mistral_Markitdown directory:
cp cursor-setup-updates/SKILL.md                      <your-skills-path>/cursor-setup/SKILL.md
cp cursor-setup-updates/templates/*.sh                 <your-skills-path>/cursor-setup/templates/
```

Then delete this `cursor-setup-updates/` folder — it's just a delivery vehicle.

---

## Changes made

### 1. All hook templates: `jq` → `python`/`python3` fallback

**Problem:** `jq` is not available on Windows (Git Bash) or reliably on macOS. Every hook that parsed JSON from stdin via `jq` would fail with `jq: command not found`, and since hooks use `failClosed: true`, this silently blocked all shell commands, MCP tools, and subagent spawns.

**Fix:** Replaced all `jq` calls with inline `python3 -c` / `python -c` scripts using stdlib `json` module. Every hook now starts with:

```bash
PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")
if [ -z "$PY" ]; then
  echo '{"permission":"allow"}'  # graceful fallback
  exit 0
fi
```

**Files changed:** `before-shell-guard.sh`, `after-file-format.sh`, `before-mcp-guard.sh`, `subagent-gate.sh`

### 2. `stop-scoped-tests.sh`: heredoc → `json.dumps()`, cross-platform `mktemp`

**Problem:** The heredoc JSON output (`cat <<EOF ... EOF`) didn't escape control characters in test output (newlines, tabs, ANSI codes). This caused `JSON Parse Error: Bad control character in string literal` in Cursor's hook parser.

**Fix:** Replaced the heredoc with `python -c "import json; print(json.dumps(...))"` which properly escapes all characters.

**Also fixed:** `mktemp /tmp/...` → `mktemp /tmp/... 2>/dev/null || mktemp` since `/tmp/` doesn't exist on Windows.

**Also fixed:** Go section used `xargs -I{}` which isn't in all Git Bash installations. Replaced with `while read`.

### 3. `SKILL.md`: new "Cross-platform compatibility" section

**Added section** documenting all cross-platform rules for hook templates:
- No `jq` dependency
- Python fallback pattern
- Cross-platform `mktemp`
- No heredoc JSON output
- `bash` prefix in hooks.json
- Go `xargs` avoidance

### 4. `SKILL.md`: `.gitignore` guidance in Phase 3

**Problem:** The skill never reminded users to add `.cursor/` to `.gitignore`. This caused hook scripts, rules, and agent definitions to show up in git diffs and commits — especially problematic when Cursor's own agent modifies hook files during sessions.

**Added to Phase 3 post-write checklist:**
- Remind to add `.cursor/` to `.gitignore`
- Run `git rm -r --cached .cursor/` if files were already tracked

### 5. `SKILL.md`: edge case for Cursor modifying its own hooks

**Added edge case:** Cursor's agent can edit files in `.cursor/hooks/` during sessions, reverting or corrupting hook scripts. Suggested mitigations: add to `.cursorignore` or add a baseline rule telling the agent not to edit hook scripts.

### 6. `SKILL.md`: fixed truncation

The original SKILL.md was truncated at line 221 mid-sentence (`**Subagent model: inherit is not always honored.**`). Restored the complete "Known limitations" section with all bullet points.
