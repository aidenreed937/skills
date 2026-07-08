#!/usr/bin/env bash
set -euo pipefail

if [ -z "${TERM:-}" ] || [ "${TERM:-}" = "dumb" ]; then
  export TERM="${AGY_REVIEW_TERM:-xterm-256color}"
fi

if ! command -v agy >/dev/null 2>&1; then
  echo "agy not found in PATH. Install or configure Antigravity CLI first." >&2
  exit 127
fi

if [ "$#" -eq 0 ] && [ -z "${AGY_REVIEW_PROMPT_FILE:-}" ]; then
  echo "Usage: $0 <review prompt> [additional prompt args...]" >&2
  echo "       AGY_REVIEW_PROMPT_FILE=/path/to/prompt.txt $0" >&2
  exit 64
fi

model="${AGY_REVIEW_MODEL:-Gemini 3.1 Pro (High)}"
timeout="${AGY_REVIEW_TIMEOUT:-10m}"
raw_project_name="$(basename "$PWD")"
project_name="$(printf '%s' "$raw_project_name" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//')"
if [ -z "$project_name" ]; then
  project_name="project"
fi
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
review_dir="${AGY_REVIEW_DIR:-$PWD/.agy-reviews}"
review_file="${AGY_REVIEW_FILE:-$review_dir/${project_name}-${timestamp}-$$.md}"
log_dir="${TMPDIR:-/tmp}"
log_dir="${log_dir%/}"
log_file="${AGY_REVIEW_LOG:-$log_dir/agy-review-${project_name}-${timestamp}-$$.log}"
output_capture="$log_dir/agy-review-${project_name}-${timestamp}-$$.out.tmp"
preflight_output="$log_dir/agy-review-${project_name}-${timestamp}-$$.preflight.out.tmp"
preflight_log_file="${AGY_REVIEW_PREFLIGHT_LOG:-$log_dir/agy-review-${project_name}-${timestamp}-$$.preflight.log}"
codegraph_used="${AGY_REVIEW_CODEGRAPH:-not checked}"
if [ -n "${AGY_REVIEW_TARGET_FILES_FILE:-}" ]; then
  target_files="$(cat "$AGY_REVIEW_TARGET_FILES_FILE")"
else
  target_files="${AGY_REVIEW_TARGET_FILES:-not provided}"
fi
if [ -n "${AGY_REVIEW_CONTEXT_FILE:-}" ]; then
  local_context="$(cat "$AGY_REVIEW_CONTEXT_FILE")"
else
  local_context="${AGY_REVIEW_CONTEXT:-}"
fi
terminal_term="${TERM:-not set}"
proxy_summary="${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-not set}}}}"
no_proxy_summary="${NO_PROXY:-${no_proxy:-not set}}"
agy_path="$(command -v agy 2>/dev/null || true)"
agy_version="$(agy --version 2>/dev/null || true)"
if [ -z "$agy_version" ]; then
  agy_version="not available"
fi
background_session="${AGY_REVIEW_BACKGROUND_SESSION:-not set}"

git_branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
git_commit="$(git rev-parse --short HEAD 2>/dev/null || true)"
if [ -z "$git_branch" ]; then
  git_branch="not a git repository"
fi
if [ -z "$git_commit" ]; then
  git_commit="not a git repository"
fi
if git diff --quiet --ignore-submodules -- 2>/dev/null && git diff --cached --quiet --ignore-submodules -- 2>/dev/null; then
  git_dirty="false"
else
  git_dirty="true"
fi
agy_command="agy --sandbox --new-project --print-timeout \"$timeout\" --log-file \"$log_file\" --model \"$model\" --print \"<prompt>\""

if [ -n "${AGY_REVIEW_PROMPT_FILE:-}" ]; then
  user_prompt="$(cat "$AGY_REVIEW_PROMPT_FILE")"
else
  user_prompt="$*"
fi
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

mkdir -p "$review_dir"
mkdir -p "$(dirname "$review_file")"
mkdir -p "$(dirname "$log_file")"

update_review_status() {
  local next_status="$1"
  local tmp_file="${review_file}.status.$$"
  awk -v next_status="$next_status" '
    !updated && $0 == "- Status: running" {
      print "- Status: " next_status
      updated = 1
      next
    }
    { print }
  ' "$review_file" > "$tmp_file"
  mv "$tmp_file" "$review_file"
}

{
  echo "# Antigravity Review"
  echo
  echo "- Project: $PWD"
  echo "- Model: $model"
  echo "- Created: $timestamp"
  echo "- Log: $log_file"
  echo "- Status: running"
  echo "- Git branch: $git_branch"
  echo "- Git commit: $git_commit"
  echo "- Git dirty: $git_dirty"
  echo "- Codegraph: $codegraph_used"
  echo "- Target files: $target_files"
  echo "- TERM: $terminal_term"
  echo "- Proxy: $proxy_summary"
  echo "- NO_PROXY: $no_proxy_summary"
  echo "- AGY path: $agy_path"
  echo "- AGY version: $agy_version"
  echo "- Background session: $background_session"
  echo "- AGY command: \`$agy_command\`"
  echo
  echo "## Startup Diagnostics"
  echo
  echo '```text'
  echo "pwd=$PWD"
  echo "agy_path=$agy_path"
  echo "agy_version=$agy_version"
  echo "term=$terminal_term"
  echo "proxy=$proxy_summary"
  echo "no_proxy=$no_proxy_summary"
  echo "review_file=$review_file"
  echo "log_file=$log_file"
  echo "preflight_log_file=$preflight_log_file"
  echo "background_session=$background_session"
  echo '```'
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

if [ "${AGY_REVIEW_PREFLIGHT:-false}" = "1" ] || [ "${AGY_REVIEW_PREFLIGHT:-false}" = "true" ]; then
  preflight_timeout="${AGY_REVIEW_PREFLIGHT_TIMEOUT:-30s}"
  preflight_prompt="${AGY_REVIEW_PREFLIGHT_PROMPT:-Smoke test for Antigravity review wrapper. Reply with one short sentence if authentication, proxy connectivity, and print mode work. Do not inspect files or modify anything.}"
  {
    echo "## Preflight"
    echo
    echo "- Timeout: $preflight_timeout"
    echo "- Log: $preflight_log_file"
    echo
  } >> "$review_file"

  set +e
  agy \
    --sandbox \
    --new-project \
    --print-timeout "$preflight_timeout" \
    --log-file "$preflight_log_file" \
    --model "$model" \
    --print "$preflight_prompt" 2>&1 | tee -a "$review_file" "$preflight_output"
  preflight_status="${PIPESTATUS[0]}"
  set -e

  {
    echo
    echo "- Preflight status: $([ "$preflight_status" -eq 0 ] && echo success || echo failed)"
    if [ "$preflight_status" -ne 0 ]; then
      echo "- Exit code: $preflight_status"
    fi
    echo
  } >> "$review_file"

  if [ "$preflight_status" -ne 0 ]; then
    echo "Review preflight failed with exit code $preflight_status. Output written to: $review_file" >&2
    update_review_status "failed"
    rm -f "$preflight_output"
    exit "$preflight_status"
  fi
fi

set +e
agy \
  --sandbox \
  --new-project \
  --print-timeout "$timeout" \
  --log-file "$log_file" \
  --model "$model" \
  --print "$prompt" 2>&1 | tee -a "$review_file" "$output_capture"
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
  failure_tail="$(tail -n 160 "$output_capture" 2>/dev/null || true)"
  if printf '%s' "$failure_tail" | grep -Eiq 'sign in|not logged|login|logged in|oauth|auth|credential|keychain'; then
    echo "- The output looks auth-related. In Codex managed sandbox environments, agy must run with escalated execution so it can read the user's Antigravity login/keyring state. Rerun the same command outside the Codex sandbox while keeping agy --sandbox." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'model|available models|unknown model|not available'; then
    echo "- The output may be model-related. Run 'agy models' and verify AGY_REVIEW_MODEL or the default model name." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'timeout|timed out|deadline|context deadline'; then
    echo "- The output looks timeout-related. Increase AGY_REVIEW_TIMEOUT or reduce the prompt/context size." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'permission|denied|operation not permitted|sandbox'; then
    echo "- The output looks permission-related. In Codex managed sandbox environments, agy must run with escalated execution while keeping agy --sandbox; the outer Codex sandbox can block Antigravity state access." >&2
  fi
  echo "- Check the log file recorded in the review header: $log_file" >&2
fi

if [ "$status" -eq 0 ]; then
  update_review_status "success"
else
  update_review_status "failed"
fi
rm -f "$output_capture"
rm -f "$preflight_output"

exit "$status"
