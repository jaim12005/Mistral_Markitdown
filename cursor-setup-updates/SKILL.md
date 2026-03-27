---
name: cursor-setup
description: Set up a complete Cursor IDE configuration for any project. Use this skill whenever the user asks to configure Cursor, set up Cursor rules, create AGENTS.md, configure hooks, set up MCP servers, create .cursorignore, or mentions wanting to optimize their Cursor workflow. Also trigger when the user says things like "set up my project for Cursor", "configure my repo for AI coding", "create cursor config", "add agent instructions", or "make my repo agent-friendly". This skill interviews the user about their project, then generates and writes all config files (hooks, rules, commands, ignore files, AGENTS.md, MCP config) customized to their actual stack, commands, and workflow.
---

# Cursor Setup Skill

Generate a complete, customized Cursor IDE configuration for any project. This skill interviews the user, then writes production-ready config files tailored to their stack, commands, and workflow.

## What gets generated

All files land under the user's project root:

```
.cursor/
  hooks.json                    # Lifecycle hooks (shell guard, formatter, MCP gate, subagent gate, test loop)
  hooks/
    before-shell-guard.sh       # Blocks destructive commands
    after-file-format.sh        # Auto-formats by extension after agent edits
    before-mcp-guard.sh         # Allowlist-based MCP tool gating
    subagent-gate.sh            # Controls which subagents can spawn
    stop-scoped-tests.sh        # Scoped test runner at end of agent run
  rules/
    00-baseline.mdc             # Always-on safety baseline
    [stack-specific rules]      # Only the ones relevant to this project
  commands/
    pr-description.md
    review.md
    migration-plan.md
    refactor-plan.md
    explain.md
    test-plan.md
  agents/                       # Custom subagent definitions
    verifier.md                 # Read-only change reviewer
    test-runner.md              # Scoped test executor
    researcher.md               # Codebase exploration worker
  mcp.json                      # Only if user wants MCP servers
.cursorignore
.cursorindexingignore
.env.mcp.local                  # Only if MCP is configured
AGENTS.md
```

## Cross-platform compatibility

Hook scripts run on Windows (via Git Bash), macOS, and Linux. The templates follow these rules:

- **No `jq` dependency.** All JSON parsing uses `python3`/`python` inline scripts. `jq` is not available in Git Bash on Windows and is not reliably installed on macOS.
- **Python fallback.** Every hook starts with: `PY=$(command -v python3 2>/dev/null || command -v python 2>/dev/null || echo "")`. Windows installs Python as `python`, not `python3`. If neither is found, the hook exits gracefully (allow for permission hooks, silent exit for formatters/tests).
- **Cross-platform `mktemp`.** Use `mktemp /tmp/... 2>/dev/null || mktemp` — `/tmp/` doesn't exist on Windows.
- **No heredoc JSON output.** Test output and error messages must be emitted via `python -c "import json; print(json.dumps(...))"` — never via `cat <<EOF`. Heredocs with embedded shell variables produce unescaped control characters that cause `JSON Parse Error: Bad control character` in Cursor's hook parser.
- **`bash` prefix in hooks.json.** All commands use `"command": "bash .cursor/hooks/script.sh"`. This is required on Windows where `.sh` files may be associated with a text editor instead of a shell, and is harmless on macOS/Linux.
- **Go `xargs` avoidance.** In the stop hook's Go section, use `while read` instead of `xargs -I{}` — `xargs` is not available in all Windows Git Bash installations.

## Workflow

### Phase 1: Discover the project

Before writing anything, gather the information needed to customize the templates. Read the templates in `templates/` to understand what placeholders need filling, then interview the user.

Start by examining the user's project if a path or repo is available. Look for:
- package.json, pyproject.toml, Cargo.toml, go.mod, Gemfile, pom.xml, etc.
- Existing .cursor/ directory, AGENTS.md, CLAUDE.md, .cursorrules
- .gitignore patterns
- Test framework configs (vitest.config, jest.config, pytest.ini, etc.)
- Linter/formatter configs (.prettierrc, ruff.toml, .eslintrc, etc.)
- CI/CD configs
- Monorepo indicators (workspaces, lerna, turborepo, nx)
- Terraform, Kubernetes, Docker files

Auto-detect as much as possible. Then ask the user to confirm and fill gaps. Group questions efficiently -- aim for 1-2 rounds of questions, not a long interrogation.

**Information needed:**

1. **Project basics** (often auto-detectable):
   - Project name
   - Primary language(s) and framework(s)
   - Package manager
   - Monorepo or single-package

2. **Commands** (critical for AGENTS.md -- ask if not detectable):
   - Install dependencies
   - Start dev server
   - Run tests (all, single file, specific suite)
   - Lint / typecheck / format
   - Build
   - Code generation (if any)
   - Database migrations (if any)

3. **Directory structure** (often auto-detectable):
   - Where source code lives
   - Where tests live
   - Any "don't touch" directories
   - Generated code directories

4. **Workflow preferences** (ask):
   - Branch naming convention
   - PR conventions
   - Any existing team rules or conventions to preserve
   - Privacy sensitivity level (standard, high, enterprise)

5. **MCP servers** (ask):
   - Do they want MCP configured?
   - If yes: which integrations (tracker, docs, database, other)?

6. **Scale** (affects which rules to include):
   - Solo dev or team?
   - Small project or large/monorepo?

7. **Subagents** (ask):
   - Do they want custom subagents configured? (verifier, test-runner, researcher are the defaults)
   - Do they want the subagent gate hook to control which subagents can spawn?
   - Any custom subagent roles specific to their workflow?

### Phase 2: Read and customize templates

Read the template files from this skill's `templates/` directory:

- `templates/AGENTS.md` -- full AGENTS.md template
- `templates/AGENTS-minimal.md` -- minimal variant
- `templates/hooks.json` -- hooks config
- `templates/before-shell-guard.sh` -- destructive command blocker
- `templates/after-file-format.sh` -- extension-based formatter
- `templates/before-mcp-guard.sh` -- MCP allowlist gate
- `templates/subagent-gate.sh` -- subagent spawn control
- `templates/stop-scoped-tests.sh` -- scoped test runner
- `templates/00-baseline.mdc` -- always-on baseline rule
- `templates/10-python-backend.mdc` -- Python rule
- `templates/20-typescript-react-frontend.mdc` -- TS/React rule
- `templates/30-infrastructure-iac.mdc` -- IaC rule
- `templates/40-monorepo-navigation.mdc` -- monorepo rule
- `templates/50-api-schema-coupling.mdc` -- API coupling rule
- `templates/cursorignore` -- security ignore file
- `templates/cursorindexingignore` -- index noise ignore file
- `templates/mcp.json.example` -- MCP config example
- `templates/commands/` -- all 6 command files
- `templates/agents/` -- custom subagent definitions (verifier, test-runner, researcher)

**Customization logic:**

For AGENTS.md:
- Use the minimal template for solo/small projects, full template for team/large projects.
- Fill ALL placeholders with real values from the interview. Every `[placeholder]` must be replaced.
- Remove sections that don't apply (e.g., "Cursor Cloud" if they don't use it, "Database migrations" if there's no DB).
- Add project-specific sharp edges, debugging tips, and conventions from the interview.

For rules:
- Always include 00-baseline.mdc.
- Only include language/framework rules that match the detected stack. A Python-only project gets 10-python-backend.mdc but NOT 20-typescript-react-frontend.mdc.
- Only include 40-monorepo-navigation.mdc if the project is actually a monorepo.
- Only include 50-api-schema-coupling.mdc if there are API contracts, schemas, or codegen.
- Only include 30-infrastructure-iac.mdc if there are infra files.
- Adjust rule content to match actual tooling (e.g., replace `ruff` with `flake8` if that's what they use).

For hooks:
- Always include before-shell-guard.sh and hooks.json.
- All hook commands in hooks.json use `bash` prefix (e.g., `"command": "bash .cursor/hooks/before-shell-guard.sh"`). This is required on Windows where .sh files may be associated with a text editor instead of a shell, and harmless on macOS/Linux.
- Customize after-file-format.sh to only include formatters the project actually uses.
- Customize stop-scoped-tests.sh to match the project's actual test runner and command patterns.
- Only include before-mcp-guard.sh if MCP is configured. Populate ALLOWED_TOOLS with actual server:tool pairs.
- The subagent-gate.sh template is available but NOT included in hooks.json by default. It fires on every subagent spawn (including Plan Mode's internal Explore calls) and creates UI noise. Only add it for enterprise/regulated environments where subagent spawning must be controlled. The downstream hooks (shell guard, MCP guard) already gate dangerous operations regardless of whether the main agent or a subagent initiated them.

For subagents:
- Include the three default subagents (verifier, test-runner, researcher) unless the user opts out.
- Customize the test-runner prompt to reference the project's exact test commands from AGENTS.md.
- If the user wants custom subagent roles, create new .md files following the same frontmatter pattern (name, description, model, readonly).
- For cost-conscious setups, set all subagents to `model: fast`. For quality-first setups, set verifier to `model: inherit` and keep the rest on `fast`.
- Always set `readonly: true` for verifier and researcher. Only test-runner and custom workers should be non-readonly.
- Update the subagent policy section in AGENTS.md to list the actual subagent names and repeat critical project invariants (package manager, test commands, forbidden operations). This is essential because subagents do NOT reliably inherit User Rules.

For ignore files:
- Start from templates, then add project-specific patterns.
- If the project has existing .gitignore patterns that overlap with .cursorindexingignore, note that .cursorindexingignore inherits .gitignore automatically and avoid duplication.
- For high-sensitivity projects, expand .cursorignore to be more aggressive.

For MCP:
- Only generate mcp.json and .env.mcp.local if the user wants MCP.
- Use actual server names and URLs from the interview.
- Always use ${env:...} placeholders for secrets, never inline values.

For commands:
- Include all 6 command files as-is. They are generic and work across stacks.

### Phase 3: Write the files

Write all files to the user's project root. Use the project path from the interview or ask for it.

**Important ordering:**
1. Create directories first: `.cursor/hooks/`, `.cursor/rules/`, `.cursor/commands/`, `.cursor/agents/`
2. Write hooks scripts and make them executable (`chmod +x`)
3. Write rules
4. Write commands
5. Write subagent definitions
6. Write ignore files
7. Write AGENTS.md (references subagent names, so write after agents exist)
8. Write MCP config if applicable
9. Write hooks.json last (references the hook scripts and subagent gate)

After writing, show a summary of what was created and any manual steps remaining:
- **Remind to add `.cursor/` to `.gitignore`** and run `git rm -r --cached .cursor/` if files were already tracked. The `.cursor/` directory contains local IDE config that varies per developer and should not be committed. If already tracked, `git rm --cached` removes from the index without deleting the files.
- Remind to add `.env.mcp.local` to `.gitignore` if MCP was configured
- Remind to set User Rules in Cursor Settings
- Remind to apply settings.json changes (telemetry, workspace trust)
- Remind to `chmod +x .cursor/hooks/*.sh` if on macOS/Linux
- Note any placeholders that couldn't be filled and need manual editing
- If an existing .cursor/ directory or AGENTS.md was found, note what was preserved vs overwritten

### Phase 4: Cross-tool compatibility (optional)

If the user mentions using Claude Code, Codex, Copilot, or other AI coding tools alongside Cursor, offer to:
- Symlink AGENTS.md as CLAUDE.md for Claude Code
- Note that .cursor/ config only applies in Cursor
- Suggest .claude/rules/ or .github/instructions/ equivalents if relevant

## Edge cases

- **Existing config found:** If the project already has .cursor/rules, AGENTS.md, or .cursorrules, show what exists and ask whether to merge, replace, or skip. Never silently overwrite.
- **Unknown stack:** If the project uses a language/framework not covered by the bundled rules, generate a custom rule file following the same structure (short, action-first, scoped, under 20 bullets).
- **No project path available:** Ask the user for their project root path before writing anything.
- **User wants only a subset:** If they only want hooks, or only want AGENTS.md, generate just what they asked for. Don't force the full package.
- **Cursor agent modifying hooks:** Cursor's own agent can edit files in `.cursor/hooks/` during sessions, reverting or corrupting hook scripts. Consider adding `.cursor/hooks/*.sh` to `.cursorignore` or adding a rule in 00-baseline.mdc telling the agent not to edit hook scripts.

## Known limitations to communicate

These are real Cursor limitations as of March 2026. Mention relevant ones during setup:

- `.cursorignore` is best-effort, not a hard security boundary. Terminal and MCP bypass it.
- `afterFileEdit` does not fire on "Accept All". Pair with editor format-on-save.
- `beforeReadFile` deny is not reliably enforced. Use `.cursorignore` for secrets.
- Hook-side `ask` is not enforced for shell or MCP. The hooks use `deny` for critical blocks.
- Rule auto-apply (description-based) is probabilistic. The baseline rule uses `alwaysApply: true`; others are scoped.
- In multi-root workspaces, root AGENTS.md can leak across repos (known bug).
- **Subagents do NOT inherit User Rules.** This is a confirmed bug. Put critical policy in AGENTS.md.
- **Subagent `model: inherit` is not always honored.** On legacy pricing plans, subagents may fall back to a Composer default unless Max Mode is enabled.
- **`subagentStart` only supports allow/deny.** `ask` is treated as deny. You cannot prompt for approval before subagent spawn.
- **Nested subagents work in IDE but not reliably in CLI/Cloud** as of March 2026.
- **Practical concurrency is ~4 foreground subagents** with batch-and-wait scheduling. Not a hard limit, but community-observed behavior.
- **Each subagent has its own token budget.** Parallel subagents multiply cost. Five workers = ~5x tokens.
