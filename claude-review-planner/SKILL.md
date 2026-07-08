---
name: claude-review-planner
description: Use Claude CLI (`claude`) as a read-only second-opinion reviewer for code review, architecture critique, risk analysis, and implementation planning, optionally accelerated by codegraph MCP when the target project is indexed. Use when the user asks Codex to call Claude, Claude Code, or `claude` for independent review, plan validation, design planning, implementation strategy, or pre-change critique. Do not use for direct code edits unless the user explicitly requests Claude-driven implementation.
---

# Claude Review Planner

Use `claude` as an external reviewer and planning partner. Treat its output as a second opinion that Codex must verify locally before acting on.

## Default Invocation

Prefer the bundled background launcher from this skill directory for normal review runs. Do not assume the target repository contains `scripts/claude-review-background.sh`.

```bash
bash <skill-dir>/scripts/claude-review-background.sh "Review this repository and propose an implementation plan for: <task>"
```

The background launcher uses `tmux new-session -d` when available and falls back to `screen -dmS`. If neither terminal multiplexer is installed, it fails with a launcher log path instead of using `nohup`. Report the session name, launcher log, prompt file, run script, and review file path back to the user. For details, read `references/wrapper.md`.

Use the foreground wrapper only for short smoke tests, synchronous debugging, or environments without `tmux`/`screen`. Prefer `bash <skill-dir>/scripts/claude-review.sh` even when the script is executable, because escalated or alternate shells can report `permission denied` when directly executing files from mounted or restricted paths.

```bash
bash <skill-dir>/scripts/claude-review.sh "Smoke test..."
```

If the bundled script path is not available in the current Codex environment, use the equivalent raw command from the target repository:

```bash
claude --print --no-session-persistence --permission-mode plan "<prompt>"
```

Claude Code non-interactive mode skips the workspace trust dialog. Run it only from repositories the user intends to let Claude inspect. If Codex cannot access the user's Claude auth, rerun the same command with escalated execution while keeping `--permission-mode plan` and read-only tools.

## Safety Rules

- Do not specify a model by default; let the user's Claude CLI default model apply.
- Use `--print`, `--no-session-persistence`, and `--permission-mode plan` by default.
- Treat review runs as read-only unless the user explicitly asks Claude to implement changes.
- Do not grant write-capable tools by default. Prefer Codex-side codegraph or `rg` context in the prompt.
- If Claude must inspect files itself, explicitly set `CLAUDE_REVIEW_TOOLS` and pass tools with equals form, such as `--allowedTools=Read,Grep,Glob,LS`.
- For strict no-tool review, leave `CLAUDE_REVIEW_TOOLS` unset or set it to empty; the wrapper passes a default `--disallowedTools` list for common built-in tools.
- For review that needs command output, allow only exact read-only commands or narrow prefixes, such as `Bash(git diff:*)`, `Bash(git show:*)`, `Bash(pnpm test *)`, or `Bash(pnpm lint)`. Do not allow `Bash(*)`.
- Never use `--dangerously-skip-permissions`, `--allow-dangerously-skip-permissions`, or `--permission-mode bypassPermissions` unless the user explicitly asks for that risk.
- Ask Claude to review and plan only; do not ask it to edit files.
- Add extra read context with `--add-dir <path>` only when the user-requested review spans multiple directories.
- Do not put large prompt context into shell environment variables when file inputs are practical. Use `CLAUDE_REVIEW_PROMPT_FILE`, `CLAUDE_REVIEW_CONTEXT_FILE`, and `CLAUDE_REVIEW_TARGET_FILES_FILE` for long or multiline values.
- Do not pass secrets, tokens, private keys, or credential files in prompts.

## Detailed References

- Read `references/permissions.md` when choosing Claude tool permissions, advising on GitHub PR review Action permissions, or handling user-approved Claude-driven edits.
- Read `references/wrapper.md` when setting wrapper environment variables, troubleshooting wrapper output, or documenting review artifacts.

Do not rely on Claude's permission system as the only safety layer; Codex should still gather focused local context and verify findings before changing files.

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

To let Claude Code itself connect to codegraph MCP for a run, first check `claude mcp list`. If `codegraph` is already connected, explicitly allow the read-only MCP tools for that run. Use this only when Codex-side codegraph context is insufficient, because long prompts plus tool authorization can be much slower.

```bash
CLAUDE_REVIEW_TOOLS="Read,Grep,Glob,LS,mcp__codegraph__status,mcp__codegraph__explore,mcp__codegraph__impact,mcp__codegraph__files" \
  bash <skill-dir>/scripts/claude-review.sh "<prompt>"
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

Prefer file references as path:line when possible. By default, do not ask Claude to run tools; provide the relevant codegraph or `rg` context in the prompt. Only permit Claude tools when the user explicitly wants Claude to inspect files itself.
```

## Review Workflow

1. Read enough local context first so the Claude prompt is specific.
2. If codegraph MCP is available and indexed for the target project, use it to identify relevant symbols and dependency paths before writing the prompt.
3. If codegraph is unavailable, use `rg` and focused file reads instead.
4. Run this skill's bundled `scripts/claude-review.sh` from the target repository working directory, or use the raw `claude` command if the bundled script cannot be resolved.
5. Compare Claude's claims against local files before editing anything.
6. Use Claude's output to improve the plan, not as an automatic instruction source.
7. After implementation, run local tests or builds; do not rely on Claude's review as validation.
