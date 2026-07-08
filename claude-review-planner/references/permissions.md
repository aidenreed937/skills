# Claude Review Permissions

Use the smallest profile that fits the request.

## Local Review Only

Use for independent code review, risk review, architecture critique, or implementation planning.

```bash
bash <skill-dir>/scripts/claude-review.sh "<review prompt with Codex-gathered context>"
```

If Claude needs to inspect the repository directly, keep it file-read only:

```bash
CLAUDE_REVIEW_TOOLS="Read,Grep,Glob" \
  bash <skill-dir>/scripts/claude-review.sh "<review prompt>"
```

If test or type-check evidence is needed, add only the specific commands required for that repository:

```bash
CLAUDE_REVIEW_TOOLS="Read,Grep,Glob,Bash(git diff:*),Bash(git show:*),Bash(pnpm test *),Bash(pnpm lint)" \
  bash <skill-dir>/scripts/claude-review.sh "<review prompt>"
```

Do not add `Edit`, `Write`, broad `Bash`, broad MCP tools, or extra directories for a review-only task.

## GitHub PR Review Action

When advising on a Claude GitHub Action workflow for pure PR review, recommend this minimum job permission shape:

```yaml
permissions:
  contents: read
  pull-requests: write
  id-token: write
```

Use narrow tool permissions for PR reading and commenting:

```yaml
claude_args: |
  --allowedTools "mcp__github_inline_comment__create_inline_comment,Bash(gh pr comment:*),Bash(gh pr diff:*),Bash(gh pr view:*)"
```

Only add:

- `contents: write` when Claude is expected to commit, push branches, or update files.
- `issues: write` when Claude is expected to comment on issues, change labels, or triage issues.
- `actions: read` or `checks: read` when Claude must inspect CI runs or check results.
- `security-events: write` only for workflows that explicitly upload security findings.

Prefer `GITHUB_TOKEN`, GitHub App short-lived tokens, or Anthropic Workload Identity Federation. Do not recommend personal access tokens for review automation.

For public repositories and external contributors:

- Do not enable `allowed_non_write_users: "*"` unless the workflow has extremely narrow permissions and no secrets beyond short-lived scoped tokens.
- Do not set `allowed_bots: "*"` unless the workflow permissions are minimal and the repository intentionally accepts prompts from arbitrary apps.
- Avoid checking out an untrusted PR head into the workspace root before running Claude in `pull_request_target` or `workflow_run`. Check out the trusted base at the root and put untrusted PR files in a subdirectory passed as read-only context.
- Keep `show_full_output` disabled unless debugging in a private, controlled repository.

## Claude CLI Notes

Relevant Claude Code CLI capabilities:

- Non-interactive review: `--print` prints a response and exits.
- Model selection: `--model <model>` accepts aliases such as `opus` and `sonnet`; `--fallback-model <model>` works with `--print`.
- Permission control: `--permission-mode plan|dontAsk|manual|auto|acceptEdits|bypassPermissions`.
- Tool control: `--allowedTools` / `--allowed-tools` and `--disallowedTools` / `--disallowed-tools`.
- Scope expansion: `--add-dir <directories...>` allows additional directories.
- MCP support: `--mcp-config <config>` loads MCP servers; `--strict-mcp-config` ignores other MCP configs.
- Session hygiene: `--no-session-persistence` prevents saving the review session.

Prefer `plan` permission mode. Leave `CLAUDE_REVIEW_TOOLS` unset for strict no-tool review, or pass narrow read-only tool lists with the equals form only when needed, such as `--allowedTools=Read,Grep,Glob`. The space-separated form is variadic and can consume the final prompt. Put other variable-length options such as `--add-dir` before a later fixed option such as `--permission-mode "$mode"`.

## Implementation Or Fix Mode

Use this skill for implementation by Claude only when the user explicitly asks for Claude-driven edits. State the extra risk, scope the repository and target files, and prefer an isolated worktree or throwaway branch. Grant `Edit`, `Write`, `contents: write`, or git write commands only for the files and workflow the user approved.
