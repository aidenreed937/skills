# Claude Review Wrapper

Read this when setting wrapper environment variables, troubleshooting wrapper output, or documenting review artifacts.

## Output Files

The wrapper writes a Markdown review file by default:

```text
<workspace>/.claude-reviews/<project-name>-<utc-timestamp>-<pid>.md
```

Each run also gets a unique log file:

```text
${TMPDIR:-/tmp}/claude-review-<project-name>-<utc-timestamp>-<pid>.log
```

Use `--no-session-persistence` for every review run so unrelated project reviews do not reuse recent Claude conversation state. The output filename includes the process id, so concurrent reviews in multiple projects will not collide unless `CLAUDE_REVIEW_FILE` is manually reused.

Review files include:

- Project, model, fallback model, created time, log path, and run status.
- Git branch, commit, and dirty state.
- Codegraph state and target files.
- MCP config state, disallowed tools, background session, and the sanitized Claude command.
- Prompt, Claude output, and final run status.

## Background Reviews

For normal review runs, prefer the background launcher instead of blocking the current turn or using ad hoc `nohup`:

```bash
bash <skill-dir>/scripts/claude-review-background.sh "Review this repository and propose an implementation plan for: <task>"
```

The background launcher uses `tmux -L <socket> new-session -d` when available and falls back to `screen -dmS`. It defaults to a per-run tmux socket so it does not reuse an existing server with different sandbox or filesystem permissions. If neither terminal multiplexer is installed, it fails with a launcher log path instead of using `nohup`. Report these values back to the user:

- Session name.
- Tmux socket when mode is `tmux`.
- Launcher log path.
- Prompt file path.
- Generated run script path.
- Review file path once the foreground wrapper creates it.

Use the foreground wrapper instead only when the review is short, synchronous output is required, or no terminal multiplexer is available.

If forced to use a raw CLI command instead of the wrapper, still write the successful output to `.claude-reviews`:

```bash
mkdir -p .claude-reviews
review_file=".claude-reviews/$(basename "$PWD")-$(date -u +%Y%m%dT%H%M%SZ)-raw.md"
{
  echo "# Claude Review"
  echo
  echo "- Project: $PWD"
  echo "- Model: Claude CLI default"
  echo "- Created: $(date -u +%Y%m%dT%H%M%SZ)"
  echo "- Status: success"
  echo
  echo "## Review"
  echo
  claude --print --no-session-persistence --permission-mode plan "<prompt>"
} | tee "$review_file"
```

## Configuration

The wrapper supports these environment overrides:

- `CLAUDE_REVIEW_MODEL`: optional; unset by default so Claude CLI chooses its default model.
- `CLAUDE_REVIEW_FALLBACK_MODEL`: optional; unset by default.
- `CLAUDE_REVIEW_PERMISSION_MODE`: defaults to `plan`.
- `CLAUDE_REVIEW_TOOLS`: defaults to `Read,Grep,Glob,mcp__codegraph__status,mcp__codegraph__explore,mcp__codegraph__impact,mcp__codegraph__files`; set to `Read,Grep,Glob` to disable codegraph while keeping file reads; set empty to use strict no-tool review with the default deny list.
- `CLAUDE_REVIEW_DISALLOWED_TOOLS`: optional explicit `--disallowedTools` list. When unset and `CLAUDE_REVIEW_TOOLS` is unset or empty, the wrapper denies common built-in tools by default: `Bash,Read,Write,Edit,Grep,Glob,WebFetch,WebSearch,Task`.
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
- `CLAUDE_REVIEW_PROMPT_FILE`: reads the user task prompt from a file instead of positional shell arguments.
- `CLAUDE_REVIEW_CONTEXT_FILE`: reads local context from a file instead of `CLAUDE_REVIEW_CONTEXT`.
- `CLAUDE_REVIEW_TARGET_FILES_FILE`: reads target file metadata from a file instead of `CLAUDE_REVIEW_TARGET_FILES`.
- `CLAUDE_REVIEW_USE_LOGIN_SHELL=1`: re-executes the wrapper through the user's login shell before running `claude`; use when Codex's non-login shell misses auth, proxy, or CLI environment setup.
- `CLAUDE_REVIEW_SESSION`: session name for `scripts/claude-review-background.sh`.
- `CLAUDE_REVIEW_BACKGROUND_LOG`: launcher log path for `scripts/claude-review-background.sh`.
- `CLAUDE_REVIEW_BACKGROUND_SCRIPT`: generated run script path for `scripts/claude-review-background.sh`.
- `CLAUDE_REVIEW_BACKGROUND_PROMPT_FILE`: generated prompt file path for `scripts/claude-review-background.sh` when `CLAUDE_REVIEW_PROMPT_FILE` is not set.
- `CLAUDE_REVIEW_BACKGROUND_SESSION`: set by the background launcher and recorded in the review file.
- `CLAUDE_REVIEW_TMUX_SOCKET`: tmux socket name for `scripts/claude-review-background.sh`; defaults to a sanitized session name.

Use `claude auth status` to verify authentication when failures mention login, credentials, or subscription access.

## Review Modes

Use strict no-tool mode when Codex has already supplied enough local context and the user wants the smallest permission profile. Set `CLAUDE_REVIEW_TOOLS=""`; Claude should label findings as context-only when it cannot inspect files.

Verified file-review mode is the default. The wrapper allows `Read,Grep,Glob` plus read-only codegraph MCP tools when `CLAUDE_REVIEW_TOOLS` is unset:

```bash
bash <skill-dir>/scripts/claude-review-background.sh "<review prompt>"
```

This mode still denies write tools because the wrapper passes only the explicit read-only allowlist. Set `CLAUDE_REVIEW_TOOLS=Read,Grep,Glob` only when Claude-side codegraph is unavailable or not useful for the target repository.
