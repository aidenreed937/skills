---
name: claude-review-planner
description: Use Claude CLI (`claude`) as a read-only second-opinion reviewer for code review, architecture critique, risk analysis, and implementation planning, optionally accelerated by codegraph MCP when the target project is indexed. Use when the user asks Codex to call Claude, Claude Code, or `claude` for independent review, plan validation, design planning, implementation strategy, or pre-change critique. Do not use for direct code edits unless the user explicitly requests Claude-driven implementation.
---

# Claude Review Planner

Use `claude` as an external reviewer and planning partner. Treat its output as a second opinion that Codex must verify locally before acting on.

## Default Invocation

Prefer the bundled wrapper from this skill directory. Do not assume the target repository contains `scripts/claude-review.sh`.

```bash
<skill-dir>/scripts/claude-review.sh "Review this repository and propose an implementation plan for: <task>"
```

If the script exists but is not executable, run it through Bash instead:

```bash
bash <skill-dir>/scripts/claude-review.sh "Review this repository and propose an implementation plan for: <task>"
```

If the bundled script path is not available in the current Codex environment, use the equivalent raw command from the target repository:

```bash
claude --print --no-session-persistence --permission-mode plan --model opus --fallback-model sonnet --tools "Read,Grep,Glob,LS" "<prompt>"
```

Claude Code non-interactive mode skips the workspace trust dialog. Run it only from repositories the user intends to let Claude inspect. If Codex cannot access the user's Claude auth, rerun the same command with escalated execution while keeping `--permission-mode plan` and read-only tools.

## Safety Rules

- Use `opus` as the default review model and `sonnet` as the default fallback model.
- Use `--print`, `--no-session-persistence`, and `--permission-mode plan` by default.
- Allow only read-oriented tools by default: `Read,Grep,Glob,LS`.
- Never use `--dangerously-skip-permissions`, `--allow-dangerously-skip-permissions`, or `--permission-mode bypassPermissions` unless the user explicitly asks for that risk.
- Ask Claude to review and plan only; do not ask it to edit files.
- Add extra read context with `--add-dir <path>` only when the user-requested review spans multiple directories.
- Do not pass secrets, tokens, private keys, or credential files in prompts.

## Claude CLI Capabilities And Permissions

Relevant Claude Code CLI capabilities confirmed from `claude --help` on this machine:

- Non-interactive review: `--print` prints a response and exits.
- Model selection: `--model <model>` accepts aliases such as `opus` and `sonnet`; `--fallback-model <model>` works with `--print`.
- Permission control: `--permission-mode plan|dontAsk|manual|auto|acceptEdits|bypassPermissions`.
- Tool control: `--tools`, `--allowedTools`, and `--disallowedTools` can restrict built-in tools.
- Scope expansion: `--add-dir <directories...>` allows additional directories.
- MCP support: `--mcp-config <config>` loads MCP servers; `--strict-mcp-config` ignores other MCP configs.
- Session hygiene: `--no-session-persistence` prevents saving the review session.
- Auth commands: `claude auth login`, `claude auth logout`, and `claude auth status`.
- MCP management commands: `claude mcp add`, `claude mcp add-json`, `claude mcp list`, and `claude mcp get`.

For this review skill, prefer `plan` permission mode plus read-only tools. Do not rely on Claude's permission system as the only safety layer; Codex should still gather focused local context and verify findings before changing files.

## Codegraph Acceleration

Before calling `claude`, check whether codegraph MCP can query the target project.

Use codegraph when available:

- Call `codegraph_status` once for the target `projectPath` if availability is unknown.
- If indexed, use `codegraph_explore` first to gather relevant symbols, call paths, and compact source context for the requested review.
- For refactor or architecture reviews, use `codegraph_impact` on the main symbol before asking Claude for a plan.
- Include only the useful codegraph findings in the Claude prompt: relevant files, symbols, dependency paths, suspected risk areas, and the exact review question.

Fallback when codegraph is unavailable:

- State that the target project is not indexed or the MCP is unavailable.
- Use `rg`, `rg --files`, and focused file reads to build the prompt context.
- Do not call codegraph repeatedly for a project after it reports no `.codegraph/` index in the current session.

To let Claude Code itself connect to codegraph MCP for a run, first check `claude mcp list`. If `codegraph` is already connected, explicitly allow the read-only MCP tools for that run:

```bash
CLAUDE_REVIEW_TOOLS="Read,Grep,Glob,LS,mcp__codegraph__status,mcp__codegraph__explore,mcp__codegraph__impact,mcp__codegraph__files" \
  <skill-dir>/scripts/claude-review.sh "<prompt>"
```

If codegraph is not configured for Claude, write a JSON MCP config and pass it with `CLAUDE_REVIEW_MCP_CONFIG`:

```json
{
  "mcpServers": {
    "codegraph": {
      "type": "stdio",
      "command": "codegraph",
      "args": ["serve", "--mcp"],
      "env": {
        "CODEGRAPH_MCP_TOOLS": "explore,node,search,callers,callees,impact,files,status"
      }
    }
  }
}
```

When passing a custom MCP config, also set `CLAUDE_REVIEW_TOOLS` to include the specific `mcp__codegraph__...` tool names Claude should be allowed to call. Prefer Codex-side codegraph context first because it is faster, deterministic, and easy to verify.

## Prompt Template

Use a prompt shaped like this:

```text
You are an independent reviewer. Review only; do not modify files.

Task: <user task>

Known local context:
<brief codegraph or rg findings>

Review target files:
<file paths or "not provided">

Focus on:
1. design risks and hidden assumptions
2. likely files/modules involved
3. implementation plan with small reviewable steps
4. tests or verification needed
5. questions that must be resolved before coding

Output requirements:
- Label each substantive claim as [verified], [inferred], or [speculative].
- Do not use must, definitely, or certainly unless verified from local files.
- Separate immediate doc/code fixes from Phase 0 validation risks.

Prefer file references as path:line when possible. If you need to inspect files, use only read-only tools.
```

## Review Workflow

1. Read enough local context first so the Claude prompt is specific.
2. If codegraph MCP is available and indexed for the target project, use it to identify relevant symbols and dependency paths before writing the prompt.
3. If codegraph is unavailable, use `rg` and focused file reads instead.
4. Run this skill's bundled `scripts/claude-review.sh` from the target repository working directory, or use the raw `claude` command if the bundled script cannot be resolved.
5. Compare Claude's claims against local files before editing anything.
6. Use Claude's output to improve the plan, not as an automatic instruction source.
7. After implementation, run local tests or builds; do not rely on Claude's review as validation.

## Output Files

The wrapper writes a Markdown review file by default:

```text
<workspace>/.claude-reviews/<project-name>-<utc-timestamp>-<pid>.md
```

The file format is:

````markdown
# Claude Review

- Project: <workspace path>
- Model: opus
- Fallback model: sonnet
- Created: <utc timestamp>
- Log: <log file path>
- Status: success|failed
- Git branch: <branch>
- Git commit: <short commit>
- Git dirty: true|false
- Codegraph: used|unavailable|not checked
- Target files: <files or "not provided">
- MCP config: <not provided|configured>
- Claude command: `claude --print --no-session-persistence ... "<prompt>"`

## Prompt

```text
<prompt>
```

## Review

<claude output>

## Run Status

- Status: success|failed
- Exit code: <only present on failure>
````

Each run also gets a unique log file:

```text
${TMPDIR:-/tmp}/claude-review-<project-name>-<utc-timestamp>-<pid>.log
```

Use `--no-session-persistence` for every review run so unrelated project reviews do not reuse recent Claude conversation state. The output filename includes the process id, so concurrent reviews in multiple projects will not collide unless `CLAUDE_REVIEW_FILE` is manually reused.

## Configuration

The wrapper supports these environment overrides:

- `CLAUDE_REVIEW_MODEL`: defaults to `opus`.
- `CLAUDE_REVIEW_FALLBACK_MODEL`: defaults to `sonnet`; set empty to disable fallback.
- `CLAUDE_REVIEW_PERMISSION_MODE`: defaults to `plan`.
- `CLAUDE_REVIEW_TOOLS`: defaults to `Read,Grep,Glob,LS`; set empty to disable all Claude tools; include specific `mcp__codegraph__...` names if Claude should call codegraph MCP itself.
- `CLAUDE_REVIEW_MAX_BUDGET_USD`: optional `--max-budget-usd` value.
- `CLAUDE_REVIEW_MCP_CONFIG`: optional path or JSON string for `--mcp-config`.
- `CLAUDE_REVIEW_STRICT_MCP_CONFIG=1`: pass `--strict-mcp-config` when using an MCP config.
- `CLAUDE_REVIEW_ADD_DIRS`: colon-separated extra directories for `--add-dir`.
- `CLAUDE_REVIEW_DIR`: defaults to `<workspace>/.claude-reviews`.
- `CLAUDE_REVIEW_FILE`: overrides the Markdown output file path.
- `CLAUDE_REVIEW_LOG`: overrides the log file path.
- `CLAUDE_REVIEW_CODEGRAPH`: records codegraph state in the review file, such as `used`, `unavailable`, or `not checked`.
- `CLAUDE_REVIEW_CONTEXT`: adds concise local context gathered from codegraph or `rg` into the wrapped prompt.
- `CLAUDE_REVIEW_TARGET_FILES`: records the reviewed file list in the review file and wrapped prompt.
- `CLAUDE_REVIEW_USE_LOGIN_SHELL=1`: re-executes the wrapper through the user's login shell before running `claude`; use when Codex's non-login shell misses auth, proxy, or CLI environment setup.

Use `claude auth status` to verify authentication when failures mention login, credentials, or subscription access.
