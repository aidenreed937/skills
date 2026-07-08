#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -eq 0 ] && [ -z "${AGY_REVIEW_PROMPT_FILE:-}" ]; then
  echo "Usage: $0 <review prompt> [additional prompt args...]" >&2
  echo "       AGY_REVIEW_PROMPT_FILE=/path/to/prompt.txt $0" >&2
  exit 64
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
workspace="$PWD"
raw_project_name="$(basename "$workspace")"
project_name="$(printf '%s' "$raw_project_name" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//')"
if [ -z "$project_name" ]; then
  project_name="project"
fi
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
session_name="${AGY_REVIEW_SESSION:-agy-review-${project_name}-${timestamp}}"
default_tmux_socket="$(printf '%s' "$session_name" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^-*//; s/-*$//')"
if [ -z "$default_tmux_socket" ]; then
  default_tmux_socket="agy-review"
fi
tmux_socket="${AGY_REVIEW_TMUX_SOCKET:-$default_tmux_socket}"
log_dir="${TMPDIR:-/tmp}"
log_dir="${log_dir%/}"
launcher_log="${AGY_REVIEW_BACKGROUND_LOG:-$log_dir/agy-review-${project_name}-${timestamp}-background.log}"
run_script="${AGY_REVIEW_BACKGROUND_SCRIPT:-$log_dir/agy-review-${project_name}-${timestamp}-run.sh}"

if [ -n "${AGY_REVIEW_PROMPT_FILE:-}" ]; then
  prompt_file="$AGY_REVIEW_PROMPT_FILE"
else
  prompt_file="${AGY_REVIEW_BACKGROUND_PROMPT_FILE:-$log_dir/agy-review-${project_name}-${timestamp}-prompt.txt}"
  printf '%s\n' "$*" > "$prompt_file"
fi

mkdir -p "$(dirname "$launcher_log")"
mkdir -p "$(dirname "$run_script")"

quote() {
  printf '%q' "$1"
}

write_export() {
  local name="$1"
  if [ -n "${!name+x}" ]; then
    printf 'export %s=%q\n' "$name" "${!name}" >> "$run_script"
  fi
}

{
  echo "#!/usr/bin/env bash"
  echo "set -euo pipefail"
  printf 'cd %q\n' "$workspace"
  printf 'export AGY_REVIEW_PROMPT_FILE=%q\n' "$prompt_file"
  printf 'export AGY_REVIEW_BACKGROUND_SESSION=%q\n' "$session_name"
} > "$run_script"

for env_name in \
  AGY_REVIEW_MODEL \
  AGY_REVIEW_TIMEOUT \
  AGY_REVIEW_TERM \
  AGY_REVIEW_DIR \
  AGY_REVIEW_FILE \
  AGY_REVIEW_LOG \
  AGY_REVIEW_CODEGRAPH \
  AGY_REVIEW_USE_CODEGRAPH \
  AGY_REVIEW_CONTEXT \
  AGY_REVIEW_CONTEXT_FILE \
  AGY_REVIEW_TARGET_FILES \
  AGY_REVIEW_TARGET_FILES_FILE \
  AGY_REVIEW_PREFLIGHT \
  AGY_REVIEW_PREFLIGHT_TIMEOUT \
  AGY_REVIEW_PREFLIGHT_PROMPT \
  AGY_REVIEW_PREFLIGHT_LOG \
  AGY_REVIEW_TMUX_SOCKET \
  HTTP_PROXY \
  HTTPS_PROXY \
  ALL_PROXY \
  NO_PROXY \
  http_proxy \
  https_proxy \
  all_proxy \
  no_proxy
do
  write_export "$env_name"
done

{
  printf 'exec bash %q\n' "$script_dir/agy-review.sh"
} >> "$run_script"
chmod +x "$run_script"

{
  echo "Antigravity background launcher"
  echo "created=$timestamp"
  echo "workspace=$workspace"
  echo "session=$session_name"
  echo "tmux_socket=$tmux_socket"
  echo "prompt_file=$prompt_file"
  echo "run_script=$run_script"
  echo "launcher_log=$launcher_log"
  echo "agy_path=$(command -v agy 2>/dev/null || true)"
  echo "agy_version=$(agy --version 2>/dev/null || true)"
  echo "term=${TERM:-not set}"
  echo "proxy=${HTTPS_PROXY:-${https_proxy:-${HTTP_PROXY:-${http_proxy:-not set}}}}"
  echo "no_proxy=${NO_PROXY:-${no_proxy:-not set}}"
} > "$launcher_log"

if command -v tmux >/dev/null 2>&1; then
  runner="bash $(quote "$run_script") 2>&1 | tee -a $(quote "$launcher_log")"
  tmux -L "$tmux_socket" new-session -d -s "$session_name" "$runner"
  mode="tmux"
elif command -v screen >/dev/null 2>&1; then
  runner="bash $(quote "$run_script") 2>&1 | tee -a $(quote "$launcher_log")"
  screen -dmS "$session_name" bash -lc "$runner"
  mode="screen"
else
  {
    echo "error=tmux or screen is required for background review"
    echo "next_step=install tmux or screen, or run scripts/agy-review.sh in the foreground"
  } >> "$launcher_log"
  echo "tmux or screen is required for background review." >&2
  echo "Install tmux/screen, or run scripts/agy-review.sh in the foreground." >&2
  echo "Launcher log: $launcher_log" >&2
  exit 127
fi

{
  echo "mode=$mode"
} >> "$launcher_log"

echo "Background review started"
echo "Mode: $mode"
echo "Session: $session_name"
echo "Launcher log: $launcher_log"
echo "Prompt file: $prompt_file"
echo "Run script: $run_script"
if [ "$mode" = "tmux" ]; then
  echo "Tmux socket: $tmux_socket"
  echo "Attach: tmux -L $tmux_socket attach -t $session_name"
elif [ "$mode" = "screen" ]; then
  echo "Attach: screen -r $session_name"
fi
