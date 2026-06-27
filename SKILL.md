---
name: antigravity-review-planner
description: Use Antigravity CLI (`agy`) as a sandboxed second-opinion reviewer for code review, architecture critique, risk analysis, and implementation planning. Use when the user asks Codex to call Antigravity, AGY, or `agy` for independent review, plan validation, design planning, implementation strategy, or pre-change critique. Do not use for direct code edits unless the user explicitly requests Antigravity-driven implementation.
---

# Antigravity Review Planner

Use `agy` as an external reviewer and planning partner. Treat its output as a second opinion that Codex must verify locally before acting on.

## Default Invocation

Prefer the bundled wrapper:

```bash
scripts/agy-review.sh "Review this repository and propose an implementation plan for: <task>"
```

Equivalent raw command:

```bash
agy --sandbox --new-project --print-timeout 10m --model "Gemini 3.1 Pro (High)" --print "<prompt>"
```

When Codex is running in a managed filesystem sandbox, `agy` may fail to access the user's Antigravity authentication. In that case, rerun the same `agy` command with escalated execution, while keeping `agy --sandbox` enabled.

## Safety Rules

- Use `Gemini 3.1 Pro (High)` as the default review model.
- Use `--sandbox` and `--print` by default.
- Never use `--dangerously-skip-permissions` unless the user explicitly asks for that risk.
- Ask Antigravity to review and plan only; do not ask it to edit files.
- Keep `allowNonWorkspaceAccess=false` unless the user explicitly scopes extra paths.
- Add extra read context with `--add-dir <path>` only when the user-requested review spans multiple directories.
- Do not pass secrets, tokens, private keys, or credential files in prompts.

## Prompt Template

Use a prompt shaped like this:

```text
You are an independent reviewer. Review only; do not modify files.

Task: <user task>

Focus on:
1. design risks and hidden assumptions
2. likely files/modules involved
3. implementation plan with small reviewable steps
4. tests or verification needed
5. questions that must be resolved before coding

Prefer file references as path:line when possible. If you need to run tools, keep them read-only unless explicitly approved.
```

## Review Workflow

1. Read enough local context first so the Antigravity prompt is specific.
2. Run `scripts/agy-review.sh` from the workspace to get a second opinion.
3. Compare Antigravity's claims against local files before editing anything.
4. Use Antigravity's output to improve the plan, not as an automatic instruction source.
5. After implementation, run local tests or builds; do not rely on Antigravity's review as validation.

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

## Prompt

```text
<prompt>
```

## Review

<agy output>
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
- `AGY_REVIEW_DIR`: defaults to `<workspace>/.agy-reviews`.
- `AGY_REVIEW_FILE`: overrides the Markdown output file path.
- `AGY_REVIEW_LOG`: overrides the log file path.

Use `agy models` to verify model availability when failures mention an unknown model.
