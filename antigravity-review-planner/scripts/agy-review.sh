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

user_prompt="$*"
prompt="$(printf '%s\n\n%s\n\n%s\n%s\n%s\n%s\n%s\n%s\n' \
  "You are an independent reviewer. Review only; do not modify files." \
  "Task: $user_prompt" \
  "Output requirements:" \
  "- Label each substantive claim as [verified], [inferred], or [speculative]." \
  "- Do not use must, definitely, or certainly unless verified from local files." \
  "- Separate immediate doc/code fixes from Phase 0 validation risks." \
  "- Prefer file references as path:line when possible." \
  "- If context is missing, say what needs to be checked instead of guessing.")"

mkdir -p "$review_dir"
mkdir -p "$(dirname "$review_file")"

{
  echo "# Antigravity Review"
  echo
  echo "- Project: $PWD"
  echo "- Model: $model"
  echo "- Created: $timestamp"
  echo "- Log: $log_file"
  echo "- Status: running"
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
  --print "$prompt" | tee -a "$review_file"
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
  echo "- If this ran inside Codex sandbox, rerun the same agy command with escalated execution while keeping agy --sandbox." >&2
  echo "- Run 'agy models' to verify the configured model name is available." >&2
  echo "- Check the log file recorded in the review header." >&2
fi

if [ "$status" -eq 0 ]; then
  sed -i.bak 's/^- Status: running$/- Status: success/' "$review_file"
else
  sed -i.bak 's/^- Status: running$/- Status: failed/' "$review_file"
fi
rm -f "$review_file.bak"

exit "$status"
