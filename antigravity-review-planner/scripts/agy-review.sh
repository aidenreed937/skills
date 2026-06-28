#!/usr/bin/env bash
set -euo pipefail

if ! command -v agy >/dev/null 2>&1; then
  echo "agy not found in PATH. Install or configure Antigravity CLI first." >&2
  exit 127
fi

if [ "$#" -eq 0 ]; then
  echo "Usage: $0 <review prompt> [additional prompt args...]" >&2
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
codegraph_used="${AGY_REVIEW_CODEGRAPH:-unknown}"
target_files="${AGY_REVIEW_TARGET_FILES:-not provided}"
local_context="${AGY_REVIEW_CONTEXT:-}"

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

mkdir -p "$review_dir"
mkdir -p "$(dirname "$review_file")"
mkdir -p "$(dirname "$log_file")"

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
  echo "- AGY command: \`$agy_command\`"
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
    echo "- The output looks auth-related. If this ran inside Codex sandbox, rerun the same agy command with escalated execution while keeping agy --sandbox." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'model|available models|unknown model|not available'; then
    echo "- The output may be model-related. Run 'agy models' and verify AGY_REVIEW_MODEL or the default model name." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'timeout|timed out|deadline|context deadline'; then
    echo "- The output looks timeout-related. Increase AGY_REVIEW_TIMEOUT or reduce the prompt/context size." >&2
  fi
  if printf '%s' "$failure_tail" | grep -Eiq 'permission|denied|operation not permitted|sandbox'; then
    echo "- The output looks permission-related. Check Antigravity permissions and whether Codex sandbox is blocking AGY state access." >&2
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
