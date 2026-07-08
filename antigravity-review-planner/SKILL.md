---
name: antigravity-review-planner
description: Use Antigravity CLI (`agy`) as a sandboxed second-opinion reviewer for code review, architecture critique, risk analysis, and implementation planning, optionally accelerated by codegraph MCP when the target project is indexed. Use when the user asks Codex to call Antigravity, AGY, or `agy` for independent review, plan validation, design planning, implementation strategy, or pre-change critique. Do not use for direct code edits unless the user explicitly requests Antigravity-driven implementation.
---

# Antigravity Review Planner

Use `agy` as an external reviewer and planning partner. Treat its output as a second opinion that Codex must verify locally before acting on.

## Default Invocation

Prefer the bundled wrapper from this skill directory. Do not assume the target repository contains `scripts/agy-review.sh`.

```bash
bash <skill-dir>/scripts/agy-review.sh "Review this repository and propose an implementation plan for: <task>"
```

For Codex managed sandbox on macOS with a local proxy, prefer an explicit proxy preflight before a longer review:

```bash
AGY_REVIEW_PROXY=http://127.0.0.1:7897 \
AGY_REVIEW_NO_PROXY=localhost,127.0.0.1,::1 \
AGY_REVIEW_PREFLIGHT=1 \
AGY_REVIEW_PREFLIGHT_TIMEOUT=30s \
bash <skill-dir>/scripts/agy-review.sh "Smoke test..."
```

For long-running reviews, prefer the background launcher instead of ad hoc `nohup`:

```bash
AGY_REVIEW_PROXY=http://127.0.0.1:7897 \
AGY_REVIEW_NO_PROXY=localhost,127.0.0.1,::1 \
bash <skill-dir>/scripts/agy-review-background.sh "Review this repository and propose an implementation plan for: <task>"
```

The background launcher uses `tmux new-session -d` when available and falls back to `screen -dmS`. If neither terminal multiplexer is installed, it fails with a launcher log path instead of using `nohup`. Report the session name, launcher log, run script, and review file path back to the user.

Prefer `bash <skill-dir>/scripts/agy-review.sh` even when the script is executable, especially for escalated execution. Some elevated shells can report `permission denied` when directly executing scripts from mounted or restricted paths.

If the bundled script path is not available in the current Codex environment, use the equivalent raw command from the target repository:

```bash
TERM=xterm-256color agy --sandbox --new-project --print-timeout 10m --model "Gemini 3.1 Pro (High)" --print "<prompt>"
```

When Codex is running in a managed filesystem sandbox, `agy` must be executed outside the Codex sandbox with escalated execution, while keeping `agy --sandbox` enabled. The outer Codex sandbox cannot read the user's Antigravity login/keyring state reliably, so non-escalated `agy` runs are expected to fail or trigger fresh authentication. Do not run `agy` inside the Codex sandbox first.

## Safety Rules

- Use `Gemini 3.1 Pro (High)` as the default review model.
- Use `--sandbox` and `--print` by default.
- In Codex managed sandbox environments, require escalated execution for the `agy` process itself, but still keep AGY's `--sandbox` flag.
- If `TERM` is empty or `dumb`, set `TERM=xterm-256color` before running `agy`; this avoids starship warnings such as `Under a 'dumb' terminal (TERM=dumb)` when AGY or its child shell touches prompt rendering.
- If the Codex tool process does not inherit the user's shell proxy variables, set `AGY_REVIEW_PROXY` before invoking the wrapper. The wrapper exports it to `HTTP_PROXY`, `HTTPS_PROXY`, `http_proxy`, `https_proxy`, `ALL_PROXY`, and `all_proxy` when those variables are not already set. Set `AGY_REVIEW_NO_PROXY` for local bypasses such as `localhost,127.0.0.1,::1`.
- Run a short `AGY_REVIEW_PREFLIGHT=1` smoke test before long reviews when auth, proxy, or background execution is uncertain.
- Prefer `scripts/agy-review-background.sh` for long-running background reviews. It starts with `tmux` when available, then `screen`; if neither is available, run the foreground wrapper instead of using `nohup`.
- Do not put large prompt context into shell environment variables when file inputs are practical. Use `AGY_REVIEW_PROMPT_FILE`, `AGY_REVIEW_CONTEXT_FILE`, and `AGY_REVIEW_TARGET_FILES_FILE` for long or multiline values.
- Never use `--dangerously-skip-permissions` unless the user explicitly asks for that risk.
- Ask Antigravity to review and plan only; do not ask it to edit files.
- Keep `allowNonWorkspaceAccess=false` unless the user explicitly scopes extra paths.
- Add extra read context with `--add-dir <path>` only when the user-requested review spans multiple directories.
- Do not pass secrets, tokens, private keys, or credential files in prompts.

## Codegraph Acceleration

Before calling `agy`, check whether codegraph MCP can query the target project.

Use codegraph when available:

- Call `codegraph_status` once for the target `projectPath` if availability is unknown.
- If indexed, use `codegraph_explore` first to gather relevant symbols, call paths, and compact source context for the requested review.
- For refactor or architecture reviews, use `codegraph_impact` on the main symbol before asking Antigravity for a plan.
- Include only the useful codegraph findings in the Antigravity prompt: relevant files, symbols, dependency paths, suspected risk areas, and the exact review question.

Fallback when codegraph is unavailable:

- State that the target project is not indexed or the MCP is unavailable.
- Use `rg`, `rg --files`, and focused file reads to build the prompt context.
- Do not call codegraph repeatedly for a project after it reports no `.codegraph/` index in the current session.

## Prompt Template

Use a prompt shaped like this:

```text
You are an independent reviewer. Review only; do not modify files.

Task: <user task>

Known local context:
<brief codegraph or rg findings>

Review target files:
<file paths or "not provided">

Focus on:
1. design risks and hidden assumptions
2. likely files/modules involved
3. implementation plan with small reviewable steps
4. tests or verification needed
5. questions that must be resolved before coding

Output requirements:
- Label each substantive claim as [verified], [inferred], or [speculative].
- Do not use must, definitely, or certainly unless verified from local files.
- Separate immediate doc/code fixes from Phase 0 validation risks.

Prefer file references as path:line when possible. If you need to run tools, keep them read-only unless explicitly approved.
```

## Review Workflow

1. Read enough local context first so the Antigravity prompt is specific.
2. If codegraph MCP is available and indexed for the target project, use it to identify relevant symbols and dependency paths before writing the prompt.
3. If codegraph is unavailable, use `rg` and focused file reads instead.
4. If the environment is not already proven, run a 30 second smoke test with `AGY_REVIEW_PREFLIGHT=1` and any required proxy variables first. Fix auth, proxy, or timeout failures before starting the real review.
5. Run this skill's bundled wrapper as `bash <skill-dir>/scripts/agy-review.sh` from the target repository working directory, or use `bash <skill-dir>/scripts/agy-review-background.sh` for long-running reviews. In Codex managed sandbox environments, the tool call must use `sandbox_permissions: "require_escalated"` and keep `agy --sandbox` enabled.
6. Compare Antigravity's claims against local files before editing anything.
7. Use Antigravity's output to improve the plan, not as an automatic instruction source.
8. After implementation, run local tests or builds; do not rely on Antigravity's review as validation.

## Output Files

The wrapper writes a Markdown review file by default:

```text
<workspace>/.agy-reviews/<project-name>-<utc-timestamp>-<pid>.md
```

The file format is:

````markdown
# Antigravity Review

- Project: <workspace path>
- Model: Gemini 3.1 Pro (High)
- Created: <utc timestamp>
- Log: <log file path>
- Status: success|failed
- Git branch: <branch>
- Git commit: <short commit>
- Git dirty: true|false
- Codegraph: used|unavailable|not checked
- Target files: <files or "not provided">
- AGY command: `agy --sandbox --new-project ... --print "<prompt>"`
- TERM: xterm-256color
- Proxy: <proxy URL or "not set">
- NO_PROXY: <bypass list or "not set">
- AGY path: <path to agy>
- AGY version: <version or "not available">
- Background session: <session name or "not set">

## Startup Diagnostics

```text
pwd=<workspace path>
agy_path=<path to agy>
agy_version=<version or "not available">
term=xterm-256color
proxy=<proxy URL or "not set">
no_proxy=<bypass list or "not set">
review_file=<review file path>
log_file=<agy log path>
preflight_log_file=<preflight log path>
background_session=<session name or "not set">
```

## Prompt

```text
<prompt>
```

## Review

<agy output>

## Run Status

- Status: success|failed
- Exit code: <only present on failure>
````

Each run also gets a unique log file:

```text
${TMPDIR:-/tmp}/agy-review-<project-name>-<utc-timestamp>-<pid>.log
```

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
- `AGY_REVIEW_PROXY`: optional proxy URL for Codex-launched `agy` processes, for example `http://127.0.0.1:7897`; exported to standard uppercase and lowercase proxy variables if they are unset.
- `AGY_REVIEW_NO_PROXY`: optional local bypass list, for example `localhost,127.0.0.1,::1`; exported to `NO_PROXY` and `no_proxy` if they are unset.
- `AGY_REVIEW_PREFLIGHT`: set to `1` or `true` to run a short smoke test before the main review.
- `AGY_REVIEW_PREFLIGHT_TIMEOUT`: defaults to `30s`.
- `AGY_REVIEW_PREFLIGHT_PROMPT`: overrides the preflight prompt.
- `AGY_REVIEW_PREFLIGHT_LOG`: overrides the preflight AGY log path.
- `AGY_REVIEW_SESSION`: session name for `scripts/agy-review-background.sh`.
- `AGY_REVIEW_BACKGROUND_LOG`: launcher log path for `scripts/agy-review-background.sh`.
- `AGY_REVIEW_BACKGROUND_SCRIPT`: generated run script path for `scripts/agy-review-background.sh`.
- `AGY_REVIEW_BACKGROUND_PROMPT_FILE`: generated prompt file path for `scripts/agy-review-background.sh` when `AGY_REVIEW_PROMPT_FILE` is not set.

Use `agy models` to verify model availability when failures mention an unknown model.
