---
name: consultant
description: Provide an independent advisory memo for the lead without becoming a reviewer, approver, or delivery owner. Use when Codex needs a non-blocking second opinion on tradeoffs, ambiguity, or cross-cutting concerns before choosing a route.
---

# Consultant

## Core stance

- Act as an independent advisor, not as a pipeline owner.
- Produce one concise second-opinion memo and stop there.
- Stay advisory-only: do not route work, do not accept artifacts, and do not block progress.

## Toggle file check

Before any invocation, read `.agents/.agents-mode.yaml` first:

- **No file** (default): consultant is disabled for ordinary optional second-opinion usage. Notify "Second opinion skipped — consultant disabled (`/second-opinion enable` to activate)" and return `5. Advisory status: NON-BLOCKING` immediately. For the mandatory batch-close external consultant-check, do not silently skip: return an advisory memo that records the disabled state and tells the lead to keep the batch open and escalate to the user.
- **`consultantMode: external`**: external-only. Attempt the selected external CLI. If it fails or is unavailable, return an unavailable memo and require the lead to keep routing honest instead of downgrading to an internal consultant path.
- **`consultantMode: internal`**: internal subagent only for ordinary optional usage. A mandatory batch-close external consultant-check is unavailable in this mode; return an unavailable memo and require the lead to keep the batch open and escalate.
- **`consultantMode: disabled`**: explicitly disabled. Same behavior as the no-file case.

The toggle file is project-local state stored in `.agents/.agents-mode.yaml`. Keep it local-only and do not commit it to git.

The shared dispatch contract lives in [../lead/external-dispatch.md](../lead/external-dispatch.md). Treat the canonical file as the shared routing schema plus the profile, opinion-count, and Codex-only Claude transport/profile keys:

- `consultantMode`
- `delegationMode`
- `mcpMode`
- `preferExternalWorker`
- `preferExternalReviewer`
- `externalProvider`
- `externalPriorityProfile`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalCodexWorkdirMode`
- `externalClaudeWorkdirMode`
- `externalGeminiWorkdirMode`
- `externalModelMode`
- `externalGeminiFallbackMode`
- `externalClaudeSecretMode`
- `externalClaudeApiMode`
- `externalClaudeProfile`

Read and normalize `.agents/.agents-mode.yaml` before routing. Comment-free, partial, or older-layout files are legacy input that must be rewritten to the current canonical format before the flags are trusted.
If the canonical file is missing, read legacy `.agents/.agents-mode` as compatibility input only, normalize it forward into `.agents/.agents-mode.yaml`, and do not recreate the legacy file.

When changing `consultantMode`, preserve the other keys, including the profile, opinion-count, workdir, model-policy, Gemini-fallback, transport, and Claude-profile fields if they exist. When creating the file from scratch, initialize the full canonical shape and default `delegationMode` to `manual`, `mcpMode` to `auto`, `externalProvider` to `auto`, `externalPriorityProfile` to `balanced`, the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks, `externalCodexWorkdirMode` / `externalClaudeWorkdirMode` / `externalGeminiWorkdirMode` to `neutral`, `externalModelMode` to `runtime-default`, `externalGeminiFallbackMode` to `auto`, `externalClaudeSecretMode` to `auto`, `externalClaudeApiMode` to `auto`, and `externalClaudeProfile` to `sonnet-high` unless the user explicitly requested a different Claude profile override.
Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.

## When to invoke

Use `$consultant` when the lead wants a second opinion for:

- hard planning or complex workspace-modifying tasks
- cross-cutting tradeoffs spanning multiple specialist roles
- ambiguity where the strongest factual slice is already available
- comparing options before choosing a route

Do not invoke for:

- trivial or simple tasks
- routine git or admin work
- ordinary read-only investigation
- work already well covered by a current specialist role

## Input contract

- The lead or main conversation invokes this role explicitly.
- Take only the canonical brief or the accepted artifact needed for the question at hand.
- Treat the task as a request for judgment, tradeoff framing, or risk surfacing rather than delivery ownership.

## Return exactly one artifact

- Return one advisory memo covering recommended direction, alternatives considered, major tradeoffs, key risks, assumptions, and confidence level.
- Every consultant memo must include a provenance header:
  - **Execution role:** `consultant`
  - **Assigned / replaced internal role:** `none`
  - **Requested provider:** <internal | claude | gemini>
  - **Resolved provider:** <Claude CLI | Gemini CLI | none>
  - **Requested consultant mode:** <external | internal | disabled>
  - **Actual execution path:** <internal consultant | external CLI (provider name) | role-play (violation)>
  - **Model / profile used:** <actual profile or model when known | runtime default | unspecified by runtime>
  - **Deviation reason:** <none | external unavailable: [reason]>
- Every consultant memo must end with an explicit continuation section:
  - **Continuation prompt:** one ready-to-send second prompt that can be used verbatim to continue the work.
  - The continuation prompt must begin with a direct imperative to continue, for example `Continue working:` or `Proceed with the next batch:`.
  - It must include the concrete next action or next review target, not just a closing sentence.

## Advisory status

- This role is intentionally non-blocking and non-approving.
- The lead decides whether to adopt or ignore the memo.
- If the memo identifies a real blocker, flag it and recommend the proper specialist role instead of acting as that role.
- For the mandatory batch-close external consultant-check, the continuation section is required even when the consultant sees no new blockers; the memo must still end with a reusable second prompt that explicitly continues the next approved work.
- If the batch-close external consultant-check cannot run because external execution is disabled or unavailable, say so explicitly in the memo and instruct the lead to keep the batch open and escalate to the user.

## Execution paths

### External provider: selected by `externalProvider`

See the shared dispatch contract in [../lead/external-dispatch.md](../lead/external-dispatch.md) for the canonical config and provider matrix.

Check the selected provider first:

- Claude path: `claude` (macOS/Linux) or `claude.exe` / `claude.cmd` (Windows)
- Gemini path: `gemini`

If `.agents/.agents-mode.yaml` selects Claude and contains `externalClaudeProfile`, map it as follows:

- `sonnet-high` → `--model sonnet --effort high`
- `opus-max` → `--model opus --effort max`
- key missing → use the current default Claude CLI invocation for this pack unless `externalModelMode: pinned-top-pro` requests the stronger Claude path

If `.agents/.agents-mode.yaml` selects Gemini (`externalProvider: gemini`), honor `externalModelMode` first.

- `runtime-default` → use Gemini CLI without forcing an explicit model/profile override.
- `pinned-top-pro` → use Gemini CLI in non-interactive mode starting from the explicit Pro path below.

Pinned Gemini example:

**Windows / macOS / Linux:**
```bash
printf '%s' "$PROMPT" | gemini -p "" --model gemini-3.1-pro --approval-mode yolo
```

Gemini fallback mode under `externalModelMode: pinned-top-pro`:
- If `externalGeminiFallbackMode: disabled`, use `gemini-3.1-pro` only. If that call fails, disclose Gemini unavailability instead of switching models or providers silently.
- If `externalGeminiFallbackMode: auto`, run the first Gemini call with `gemini-3.1-pro`. If that call fails with quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures, rerun the same one-line Gemini command once with `--model gemini-3-flash`.
- If `externalGeminiFallbackMode: force`, use `gemini-3-flash` as the primary Gemini model immediately instead of spending time on a preceding `gemini-3.1-pro` attempt.

Examples:

**macOS / Linux:**
```bash
printf '%s' "$PROMPT" | claude -p --model sonnet --effort high --permission-mode bypassPermissions
printf '%s' "$PROMPT" | claude -p --model opus --effort max --permission-mode bypassPermissions
```

**Windows (Git Bash inside Codex):**
```bash
printf '%s' "$PROMPT" | cmd.exe /c claude.exe -p --model sonnet --effort high --permission-mode bypassPermissions
printf '%s' "$PROMPT" | cmd.exe /c claude.exe -p --model opus --effort max --permission-mode bypassPermissions
```
Fallback if `claude.exe` is not on PATH: use `claude.cmd` instead.

Claude SECRET mode:
- If `externalClaudeSecretMode: auto`, run the first profile-correct Claude CLI call normally. If that call fails with quota, limit, or reset errors, perform one SECRET-backed retry by rerunning the same Claude command with `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` (for example `~/.claude/SECRET.md`) added to that command's environment in the same one-liner.
- If `externalClaudeSecretMode: force`, add the same `ANTHROPIC_*` values from the local Claude `SECRET.md` to the primary Claude call immediately. Do not perform a second SECRET-backed retry because the primary call already used that environment override.
- Do not switch providers, downgrade the Claude profile, or rewrite tracked config during either Claude path.

Claude API transport:
- If `externalClaudeApiMode: auto`, treat `claude-api` as the named secondary Claude transport after the allowed Claude CLI path is exhausted.
- If `externalClaudeApiMode: force`, use `claude-api` as the primary Claude transport immediately instead of spending time on a preceding Claude CLI call.
- `claude-api` must preserve the same provider intent and requested profile/model family; it is a Claude transport change, not a provider switch.

**Rules:**
- If `externalClaudeProfile` is present, use it instead of improvising a different Claude model or effort level.
- If `externalClaudeSecretMode: force` is selected and the local Claude `SECRET.md` cannot supply all three `ANTHROPIC_*` values, treat that as external-provider unavailability instead of silently dropping back to a plain Claude call.
- If `externalProvider: gemini` is selected, do not silently reroute to Claude; honor `externalModelMode` first, then any allowed Gemini same-provider fallback, and disclose provider failure explicitly if the route still fails.
- If the requested Claude profile is unavailable because of auth, client support, or non-limit CLI failures, treat that as external-provider unavailability and return an unavailable memo.
- If the requested Claude profile fails because of plan limits, quota, or reset errors, honor `externalClaudeSecretMode`: `auto` tries the single SECRET-backed one-line retry first, while `force` treats the already-SECRET-backed primary call as the full allowed Claude path. If that allowed Claude CLI path still fails and `externalClaudeApiMode` permits `claude-api`, try `claude-api` before declaring Claude unavailable. Do not silently downgrade to another Claude profile.
- If `externalClaudeApiMode` requires `claude-api` and that command is unavailable, disclose a dependency/config failure instead of pretending the Claude path was complete.
- If Gemini returns quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style errors, honor `externalGeminiFallbackMode`: `auto` allows one retry on `gemini-3-flash`, while `force` treats the already-flash primary call as the full allowed Gemini path. Do not silently downgrade below Gemini 3 or switch providers.
- Do not pass multiline prompts as direct command-line arguments — use `stdin` or a file.
- Do not use TTY when a non-interactive invocation is available.
- On Windows, keep command-line prompts short enough to avoid `cmd.exe` truncation.
- On Windows, keep the ordinary shell path unchanged and try the native Windows shell first. If that shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- Wait 5–15 minutes before treating a single advisory run as stalled. Do not launch a duplicate advisory call for the same memo while the first may still be running; independent external lanes may still run in parallel when their scopes are disjoint and the routing contract allows it.
- If Claude returns quota, auth, or limit errors, record that in the relevant plan or note, including the resolved `externalClaudeSecretMode`, whether a SECRET-backed Claude path was attempted, and how it ended. Do not silently fall back; return an unavailable memo and require the lead to keep routing honest.

### No implicit fallback

- `consultantMode: external` is external-only. If the selected external provider is unavailable, stalls, or fails, return an unavailable memo and let the lead reroute honestly.
- `consultantMode: internal` is the only supported internal consultant path. It must be selected explicitly in `.agents/.agents-mode.yaml`; do not downgrade into it automatically after an external failure.
- Provider-backed consultant execution in `external` mode must use direct external launch from the orchestrating runtime or an approved transport wrapper script. If the current runtime cannot do that, disclose the dependency failure instead of proxying through an internal agent/helper/subagent host.
- Never turn a failed external consultant run into a hidden internal substitute.

## Working rules

- Be concise, high-signal, and explicit about uncertainty.
- Prefer decision support over execution detail.
- Discuss the problem first for hard planning or complex workspace changes; do not jump straight to plan output.
- Stop after the memo unless the lead explicitly asks a follow-up question.

## Artifact lifecycle

Advisory memos are point-in-time opinions with no automatic expiration. If the lead references a memo after significant scope, design, or constraint changes since the memo was written, the lead should re-invoke the consultant rather than relying on a potentially stale memo.

## Non-goals

- Do not take routing authority away from `$lead`.
- Do not replace research, design, planning, implementation, QA, or reviewer roles.
- Do not issue `PASS`, `REVISE`, or `BLOCKED` as if you were a pipeline gate.
