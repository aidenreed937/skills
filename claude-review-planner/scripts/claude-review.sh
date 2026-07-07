#!/usr/bin/env bash
set -euo pipefail

if [ "${CLAUDE_REVIEW_USE_LOGIN_SHELL:-}" = "1" ] && [ -z "${CLAUDE_REVIEW_LOGIN_SHELL_ACTIVE:-}" ]; then
  login_shell="${SHELL:-/bin/zsh}"
  if [ ! -x "$login_shell" ]; then
    echo "CLAUDE_REVIEW_USE_LOGIN_SHELL=1 requested, but login shell is not executable: $login_shell" >&2
    exit 126
  fi
  export CLAUDE_REVIEW_LOGIN_SHELL_ACTIVE=1
  exec "$login_shell" -lic 'exec "$@"' claude-review-login "$0" "$@"
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "claude not found in PATH. Install or configure Claude Code CLI first." >&2
  exit 127
fi

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <review prompt> [additional prompt args...]" >&2
  exit 64
fi

model="${CLAUDE_REVIEW_MODEL-opus}"
fallback_model="${CLAUDE_REVIEW_FALLBACK_MODEL-sonnet}"
permission_mode="${CLAUDE_REVIEW_PERMISSION_MODE:-plan}"
tools="${CLAUDE_REVIEW_TOOLS-Read,Grep,Glob,LS}"
max_budget="${CLAUDE_REVIEW_MAX_BUDGET_USD:-}"
mcp_config="${CLAUDE_REVIEW_MCP_CONFIG:-}"
strict_mcp="${CLAUDE_REVIEW_STRICT_MCP_CONFIG:-}"
add_dirs="${CLAUDE_REVIEW_ADD_DIRS:-}"
raw_project_name="$(basename "$PWD")"
project_name="$(printf '%s' "$raw_project_name" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//')"
if [ -z "$project_name" ]; then
  project_name="project"
fi
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
review_dir="${CLAUDE_REVIEW_DIR:-$PWD/.claude-reviews}"
review_file="${CLAUDE_REVIEW_FILE:-$review_dir/${project_name}-${timestamp}-$$.md}"
log_dir="${TMPDIR:-/tmp}"
log_dir="${log_dir%/}"
log_file="${CLAUDE_REVIEW_LOG:-$log_dir/claude-review-${project_name}-${timestamp}-$$.log}"
output_capture="$log_dir/claude-review-${project_name}-${timestamp}-$$.out.tmp"
codegraph_used="${CLAUDE_REVIEW_CODEGRAPH:-not checked}"
target_files="${CLAUDE_REVIEW_TARGET_FILES:-not provided}"
local_context="${CLAUDE_REVIEW_CONTEXT:-}"

git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
git_commit="$(git rev-parse --short HEAD 2>/dev/null || true)"
if [ -z "$git_branch" ]; then
  git_branch="not a git repository"
fi
if [ -z "$git_commit" ]; then
  git_commit="not a git repository"
fi
if [ -n "$(git status --porcelain --untracked-files=normal 2>/dev/null)" ]; then
  git_dirty="true"
else
  git_dirty="false"
fi

user_prompt="$*"
prompt="$(printf '%s\n\n%s\n\n%s\n%s\n\n%s\n%s\n\n%s\n%s\n%s\n%s\n%s\n%s\n' \
  "You are an independent reviewer. Review only; do not modify files." \
  "Task: $user_prompt" \
  "Known local context:" \
  "${local_context:-not provided}" \
  "Review target files:" \
  "$target_files" \
  "Output requirements:" \
  "- Label each substantive claim as [verified], [inferred], or [speculative]." \
  "- Do not use must, definitely, or certainly unless verified from local files." \
  "- Separate immediate doc/code fixes from Phase 0 validation risks." \
  "- Prefer file references as path:line when possible." \
  "- If context is missing, say what needs to be checked instead of guessing.")"

cmd=(claude --print --no-session-persistence --model "$model")
if [ -n "$fallback_model" ]; then
  cmd+=(--fallback-model "$fallback_model")
fi
if [ -n "$max_budget" ]; then
  cmd+=(--max-budget-usd "$max_budget")
fi
if [ -n "$mcp_config" ]; then
  cmd+=(--mcp-config "$mcp_config")
  if [ "$strict_mcp" = "1" ]; then
    cmd+=(--strict-mcp-config)
  fi
fi
if [ -n "$add_dirs" ]; then
  old_ifs="$IFS"
  IFS=':'
  for add_dir in $add_dirs; do
    if [ -n "$add_dir" ]; then
      cmd+=(--add-dir "$add_dir")
    fi
  done
  IFS="$old_ifs"
fi
cmd+=("--allowedTools=$tools")
cmd+=(--permission-mode "$permission_mode")

claude_command="claude --print --no-session-persistence --model \"$model\""
if [ -n "$fallback_model" ]; then
  claude_command="$claude_command --fallback-model \"$fallback_model\""
fi
if [ -n "$max_budget" ]; then
  claude_command="$claude_command --max-budget-usd \"$max_budget\""
fi
if [ -n "$mcp_config" ]; then
  claude_command="$claude_command --mcp-config \"<configured>\""
  if [ "$strict_mcp" = "1" ]; then
    claude_command="$claude_command --strict-mcp-config"
  fi
fi
if [ -n "$add_dirs" ]; then
  claude_command="$claude_command --add-dir \"<configured>\""
fi
claude_command="$claude_command --allowedTools=\"$tools\""
claude_command="$claude_command --permission-mode \"$permission_mode\""
claude_command="$claude_command \"<prompt>\""
mcp_status="not provided"
if [ -n "$mcp_config" ]; then
  mcp_status="configured"
fi

mkdir -p "$review_dir"
mkdir -p "$(dirname "$review_file")"
mkdir -p "$(dirname "$log_file")"

{
  echo "# Claude Review"
  echo
  echo "- Project: $PWD"
  echo "- Model: $model"
  echo "- Fallback model: ${fallback_model:-not configured}"
  echo "- Created: $timestamp"
  echo "- Log: $log_file"
  echo "- Status: running"
  echo "- Git branch: $git_branch"
  echo "- Git commit: $git_commit"
  echo "- Git dirty: $git_dirty"
  echo "- Codegraph: $codegraph_used"
  echo "- Target files: $target_files"
  echo "- MCP config: $mcp_status"
  echo "- Claude command: \`$claude_command\`"
  echo
  echo "## Prompt"
  echo
  echo '```text'
  echo "$prompt"
  echo '```'
  echo
  echo "## Review"
  echo
} > "$review_file"

set +e
"${cmd[@]}" "$prompt" 2>&1 | tee -a "$review_file" "$output_capture" "$log_file"
status="${PIPESTATUS[0]}"
set -e

{
  echo
  echo "## Run Status"
  echo
  if [ "$status" -eq 0 ]; then
    echo "- Status: success"
  else
    echo "- Status: failed"
    echo "- Exit code: $status"
  fi
} >> "$review_file"

if [ "$status" -eq 0 ]; then
  echo "Review written to: $review_file" >&2
else
  echo "Review failed with exit code $status. Partial output written to: $review_file" >&2
  echo "Common next steps:" >&2
  failure_tail="$(
    {
      tail -n 160 "$output_capture" 2>/dev/null || true
      tail -n 200 "$log_file" 2>/dev/null || true
    } | sed -n '1,360p'
  )"
  if printf '%s' "$failure_tail" | grep -Eiq 'sign in|not logged|login|logged in|oauth|auth|credential|keychain|subscription'; then
    echo "- The output looks auth-related. Run 'claude auth status'. If this ran inside Codex sandbox, rerun the same claude command with escalated execution while keeping plan mode and read-only tools." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'model|unknown model|not available|fallback'; then
    echo "- The output may be model-related. Verify CLAUDE_REVIEW_MODEL, or try CLAUDE_REVIEW_MODEL=sonnet." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'budget|max-budget|cost|quota|rate limit|overloaded'; then
    echo "- The output looks budget, quota, or capacity related. Adjust CLAUDE_REVIEW_MAX_BUDGET_USD, retry later, or use a cheaper fallback model." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'permission|denied|operation not permitted|trust|workspace'; then
    echo "- The output looks permission-related. Check workspace trust, Codex sandbox access, and Claude permission mode." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'mcp|server|stdio|connection|spawn'; then
    echo "- The output may be MCP-related. Check CLAUDE_REVIEW_MCP_CONFIG and 'claude mcp list' or run without MCP config." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'tool|tools|unknown|invalid'; then
    echo "- The output may be tool-list related. Try CLAUDE_REVIEW_TOOLS=Read or CLAUDE_REVIEW_TOOLS= to pass an empty allow list." >&2
  fi
  echo "- Check the log file recorded in the review header: $log_file" >&2
fi

if [ "$status" -eq 0 ]; then
  sed -i.bak 's/^- Status: running$/- Status: success/' "$review_file"
else
  sed -i.bak 's/^- Status: running$/- Status: failed/' "$review_file"
fi
rm -f "$review_file.bak"
rm -f "$output_capture"

exit "$status"
