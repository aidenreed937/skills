---
name: antigravity-review-planner
description: Use Antigravity CLI (`agy`) as a sandboxed second-opinion reviewer for code review, architecture critique, risk analysis, and implementation planning, optionally accelerated by codegraph MCP when the target project is indexed. Use when the user asks Codex to call Antigravity, AGY, or `agy` for independent review, plan validation, design planning, implementation strategy, or pre-change critique. Do not use for direct code edits unless the user explicitly requests Antigravity-driven implementation.
---

# Antigravity Review Planner

Use `agy` as an external reviewer and planning partner. Treat its output as a second opinion that Codex must verify locally before acting on.

## Default Invocation

Prefer the bundled background launcher from this skill directory for normal review runs. Do not assume the target repository contains `scripts/agy-review-background.sh`.

```bash
bash <skill-dir>/scripts/agy-review-background.sh "Review this repository and propose an implementation plan for: <task>"
```

For proxy, preflight, background runs, output files, and environment variables, read `references/runtime.md`.

Use the foreground wrapper only for short smoke tests, synchronous debugging, or environments without `tmux`/`screen`. Prefer `bash <skill-dir>/scripts/agy-review.sh` even when the script is executable, especially for escalated execution. Some elevated shells can report `permission denied` when directly executing scripts from mounted or restricted paths.

```bash
bash <skill-dir>/scripts/agy-review.sh "Smoke test..."
```

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

This section intentionally matches the Claude review planner workflow. Keep codegraph and prompt-preparation behavior aligned across both review skills; diverge only for CLI-specific permission, sandbox, auth, proxy, or background-execution requirements.

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
