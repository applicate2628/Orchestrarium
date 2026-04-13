---
name: consultant
description: Provide an independent advisory memo for the lead without becoming a reviewer, approver, or delivery owner. Use when Gemini CLI needs a non-blocking second opinion on tradeoffs, ambiguity, or cross-cutting concerns before choosing a route.
---

# Consultant

## Core stance

- Advisory-only.
- One memo per invocation, then stop.
- No routing authority, no gate authority, no hidden fallback.

## Toggle state

Read and normalize `.gemini/.agents-mode` before routing. Comment-free, partial, or older-layout files are legacy input that must be rewritten to the current canonical format before the flags are trusted.

Relevant keys:

- `consultantMode`
- `externalProvider`
- `externalPriorityProfile`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalGeminiFallbackMode`
- `externalClaudeSecretMode`
- `externalClaudeApiMode`

Gemini-line provider rules:

- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider
- `externalPriorityProfile` defaults to `balanced`
- `balanced` mirrors the ordinary shared matrix; `gemini-crosscheck` keeps Gemini in the non-visual advisory and pre-PR review cross-check lanes
- `externalProvider: codex` means Codex CLI explicitly
- `externalProvider: claude` means Claude CLI explicitly
- `externalProvider: gemini` is allowed only as an explicit self-provider override
- `externalModelMode` is the shared cross-provider model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion
- `externalGeminiFallbackMode` matters only when the resolved provider is Gemini and the model policy is pinned
- Under `externalModelMode: pinned-top-pro`, `externalGeminiFallbackMode: auto` keeps `gemini-3.1-pro` first and allows one retry on `gemini-3-flash` only for quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures
- `externalClaudeSecretMode` matters only when the resolved provider is Claude
- `externalClaudeApiMode` matters only when the resolved provider is Claude
- The shared lane matrix still prefers Gemini for image/icon/decorative advisory work when that routing remains honest
- Same-provider Gemini routing must be explicit; ordinary `auto` must still avoid self-bounce
- When the active lane policy asks for more than one external opinion, the lead may invoke this skill more than once and aggregate the returned memos

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
- For the mandatory batch-close external consultant-check, do not silently downgrade to an internal-only path.
- If the external consultant path is unavailable for that mandatory closeout sweep, say so explicitly and keep the batch open for escalation.
- If the active lane policy requests more than one external consultant-check, each invocation still returns one memo; the lead aggregates the memos and fails closed when the requested count cannot be satisfied.
