---
name: second-opinion
description: Get an independent second opinion via the consultant role, or manage the Gemini-line consultant toggle state.
---

# Second Opinion

Use this skill to invoke `$consultant` or to change Gemini-line consultant mode.

## Toggle keys

Manage these keys in `.gemini/.agents-mode`:

- `consultantMode`
- `delegationMode`
- `mcpMode`
- `preferExternalWorker`
- `preferExternalReviewer`
- `externalProvider`
- `externalPriorityProfile`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalClaudeSecretMode`
- `externalClaudeApiMode`

Gemini-line rules:

- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider
- `externalPriorityProfile` defaults to `balanced`
- `balanced` is the ordinary profile; `gemini-crosscheck` is the profile that intentionally keeps Gemini in the non-visual advisory and review cross-check set
- explicit providers are `codex`, `claude`, and `gemini`
- `externalProvider: gemini` is allowed only as an explicit self-provider override
- `externalClaudeSecretMode` matters only when provider resolves to Claude
- `externalClaudeApiMode` matters only when provider resolves to Claude
- documented repo-local visual heuristics may still keep eligible image/icon/decorative visual lanes on Gemini itself when that routing remains honest
- same-provider Gemini routing must be explicit; ordinary `auto` must still avoid self-bounce
- preserve unknown keys and keep the three new profile/count keys in expanded multi-key form rather than collapsing them into a consultant-only shape
- `externalOpinionCounts` is lane-specific; when a lane asks for more than one opinion, the lead may invoke the matching external skill repeatedly and aggregate fail closed

## Toggle actions

- `enable` -> `consultantMode: external`
- `internal` -> `consultantMode: internal`
- `disable` -> `consultantMode: disabled`
- `status` -> read and normalize `.gemini/.agents-mode`, then print the current resolved values

Preserve unknown keys on write and normalize comment-free, partial, or older-layout files to the current canonical format on read. Keep one key per line with inline allowed-value comments.

## Advisory run

When not in toggle mode:

1. read and normalize the current toggle state
2. collect the bounded question and accepted context
3. invoke `$consultant`
4. return the memo

Consultant output remains non-blocking.
