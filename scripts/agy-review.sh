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
project_name="$(basename "$PWD" | tr -cs 'A-Za-z0-9._-' '-')"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
review_dir="${AGY_REVIEW_DIR:-$PWD/.agy-reviews}"
review_file="${AGY_REVIEW_FILE:-$review_dir/${project_name}-${timestamp}-$$.md}"
log_file="${AGY_REVIEW_LOG:-${TMPDIR:-/tmp}/agy-review-${project_name}-${timestamp}-$$.log}"

prompt="$*"

mkdir -p "$review_dir"
mkdir -p "$(dirname "$review_file")"

{
  echo "# Antigravity Review"
  echo
  echo "- Project: $PWD"
  echo "- Model: $model"
  echo "- Created: $timestamp"
  echo "- Log: $log_file"
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

echo "Review written to: $review_file" >&2
exit "$status"
