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
log_file="${AGY_REVIEW_LOG:-/tmp/agy-review.log}"

prompt="$*"

exec agy \
  --sandbox \
  --print-timeout "$timeout" \
  --log-file "$log_file" \
  --model "$model" \
  --print "$prompt"
