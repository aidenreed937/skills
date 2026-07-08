# Antigravity Review Runtime

Read this when using proxy/preflight/background mode, setting wrapper environment variables, troubleshooting wrapper output, or documenting review artifacts.

## Proxy And Preflight

For Codex managed sandbox on macOS with a local proxy, prefer an explicit proxy preflight before a longer review:

```bash
AGY_REVIEW_PROXY=http://127.0.0.1:7897 \
AGY_REVIEW_NO_PROXY=localhost,127.0.0.1,::1 \
AGY_REVIEW_PREFLIGHT=1 \
AGY_REVIEW_PREFLIGHT_TIMEOUT=30s \
bash <skill-dir>/scripts/agy-review.sh "Smoke test..."
```

The wrapper exports `AGY_REVIEW_PROXY` to standard uppercase and lowercase proxy variables when they are unset. Set `AGY_REVIEW_NO_PROXY` for local bypasses such as `localhost,127.0.0.1,::1`.

## Background Reviews

For normal review runs, prefer the background launcher instead of blocking the current turn or using ad hoc `nohup`:

```bash
AGY_REVIEW_PROXY=http://127.0.0.1:7897 \
AGY_REVIEW_NO_PROXY=localhost,127.0.0.1,::1 \
bash <skill-dir>/scripts/agy-review-background.sh "Review this repository and propose an implementation plan for: <task>"
```

The background launcher uses `tmux new-session -d` when available and falls back to `screen -dmS`. If neither terminal multiplexer is installed, it fails with a launcher log path instead of using `nohup`. Report the session name, launcher log, run script, and review file path back to the user.

## Output Files

The wrapper writes a Markdown review file by default:

```text
<workspace>/.agy-reviews/<project-name>-<utc-timestamp>-<pid>.md
```

Each run also gets a unique log file:

```text
${TMPDIR:-/tmp}/agy-review-<project-name>-<utc-timestamp>-<pid>.log
```

Review files include:

- Project, model, created time, log path, and run status.
- Git branch, commit, and dirty state.
- Codegraph state and target files.
- AGY command, TERM, proxy state, AGY path/version, and background session.
- Startup diagnostics, prompt, AGY output, and final run status.

Use `--new-project` for every review run so unrelated project reviews do not reuse recent Antigravity conversation state.

## Configuration

The wrapper supports these environment overrides:

- `AGY_REVIEW_MODEL`: defaults to `Gemini 3.1 Pro (High)`.
- `AGY_REVIEW_TIMEOUT`: defaults to `10m`.
- `AGY_REVIEW_TERM`: defaults to `xterm-256color` when the inherited `TERM` is empty or `dumb`.
- `AGY_REVIEW_DIR`: defaults to `<workspace>/.agy-reviews`.
- `AGY_REVIEW_FILE`: overrides the Markdown output file path.
- `AGY_REVIEW_LOG`: overrides the log file path.
- `AGY_REVIEW_CODEGRAPH`: records codegraph state in the review file, such as `used`, `unavailable`, or `not checked`.
- `AGY_REVIEW_CONTEXT`: adds concise local context gathered from codegraph or `rg` into the wrapped prompt.
- `AGY_REVIEW_TARGET_FILES`: records the reviewed file list in the review file and wrapped prompt.
- `AGY_REVIEW_PROMPT_FILE`: reads the user task prompt from a file instead of positional shell arguments.
- `AGY_REVIEW_CONTEXT_FILE`: reads local context from a file instead of `AGY_REVIEW_CONTEXT`.
- `AGY_REVIEW_TARGET_FILES_FILE`: reads target file metadata from a file instead of `AGY_REVIEW_TARGET_FILES`.
- `AGY_REVIEW_PROXY`: optional proxy URL for Codex-launched `agy` processes.
- `AGY_REVIEW_NO_PROXY`: optional local bypass list.
- `AGY_REVIEW_PREFLIGHT`: set to `1` or `true` to run a short smoke test before the main review.
- `AGY_REVIEW_PREFLIGHT_TIMEOUT`: defaults to `30s`.
- `AGY_REVIEW_PREFLIGHT_PROMPT`: overrides the preflight prompt.
- `AGY_REVIEW_PREFLIGHT_LOG`: overrides the preflight AGY log path.
- `AGY_REVIEW_SESSION`: session name for `scripts/agy-review-background.sh`.
- `AGY_REVIEW_BACKGROUND_LOG`: launcher log path for `scripts/agy-review-background.sh`.
- `AGY_REVIEW_BACKGROUND_SCRIPT`: generated run script path for `scripts/agy-review-background.sh`.
- `AGY_REVIEW_BACKGROUND_PROMPT_FILE`: generated prompt file path for `scripts/agy-review-background.sh` when `AGY_REVIEW_PROMPT_FILE` is not set.

Use `agy models` to verify model availability when failures mention an unknown model.
