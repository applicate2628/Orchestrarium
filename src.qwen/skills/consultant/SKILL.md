---
name: consultant
description: Provide an independent advisory memo for the lead without becoming a reviewer, approver, or delivery owner. Use when Qwen Code needs a non-blocking second opinion on tradeoffs, ambiguity, or cross-cutting concerns before choosing a route.
---

# Consultant

## Core stance

- Advisory-only.
- One memo per invocation, then stop.
- No routing authority, no gate authority, no hidden fallback.

## Toggle state

Read and normalize `.qwen/.agents-mode.yaml` before routing. Comment-free, partial, or older-layout files are legacy input that must be rewritten to the current canonical format before the flags are trusted.
Read and normalize `.qwen/.agents-mode.yaml` before routing. If local `.qwen/.agents-mode.yaml` is missing, read local legacy `.qwen/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.qwen/.agents-mode.yaml` and then global legacy `~/.qwen/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope and do not recreate any legacy file.

Relevant keys:

- `consultantMode`
- `parallelMode`
- `externalClaudeApiMode`
- `externalProvider`
- `externalPriorityProfile`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalModelMode`

Qwen-line provider rules:

- `externalProvider: auto` resolves through the active named priority profile, not a Qwen-line default provider
- `externalPriorityProfile` defaults to `balanced`
- the shipped `balanced` profile is production-only and keeps `auto` routing on `codex | claude`
- `externalProvider: codex` means Codex CLI explicitly
- `externalProvider: claude` means Claude CLI explicitly
- `externalProvider: gemini` and `externalProvider: qwen` are explicit example-only overrides; both are `WEAK MODEL / NOT RECOMMENDED`
- `externalModelMode` is the shared cross-provider model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native production path for the resolved provider
- `externalClaudeApiMode` controls only the supplemental `claude-secret` advisory/review profile candidate; allowed values are `disabled | auto | force`, with `auto` as the default
- `claude-secret` appears only after primary `claude`/`codex` when an advisory/review order reaches it; it is independent of primary `claude` and is not a retry, fallback, or worker transport
- `parallelMode` is the general helper fan-out rule across internal and external lanes
- if a repository wants Qwen participation in an advisory lane, express that through a scalar explicit provider override rather than any `auto` profile entry
- same-provider Qwen routing must be explicit; ordinary `auto` must still avoid self-bounce
- when the active lane policy asks for more than one external opinion, the lead may invoke this skill more than once and aggregate the returned memos on top of `parallelMode`

## Return

Return one advisory memo with:

1. Summary
2. Recommended direction
3. Alternatives considered
4. Risks / unknowns
5. Advisory status: NON-BLOCKING
6. Continuation prompt: one ready-to-send prompt that begins with a direct imperative to continue and names the next concrete action

## Working rules

- Distinguish confirmed facts, assumptions, and judgment.
- Use file-based prompt delivery for substantive external CLI prompts: write the prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism; direct prompt argv is only for tiny smoke checks or documented provider limitations.
- If the lead or repo-local lane policy explicitly requests a closeout consultant sweep, follow the configured consultant mode honestly and do not silently downgrade to a different path.
- If the selected consultant path is unavailable for that requested closeout sweep, say so explicitly and keep the batch open for escalation.
- If the active lane policy requests more than one consultant-check, each invocation still returns one memo; the lead aggregates the memos and fails closed when the requested count cannot be satisfied.
