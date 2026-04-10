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
- `externalClaudeSecretMode`

Gemini-line rules:

- `externalProvider: auto` keeps provider-backed external dispatch explicit on the Gemini line
- explicit providers are `codex` and `claude`
- `externalProvider: gemini` is invalid on the Gemini line
- `externalClaudeSecretMode` matters only when provider resolves to Claude

## Toggle actions

- `enable` -> `consultantMode: external`
- `auto` -> `consultantMode: auto`
- `internal` -> `consultantMode: internal`
- `disable` -> `consultantMode: disabled`
- `status` -> print the current resolved values

Preserve unknown keys on write and keep one key per line with inline allowed-value comments.

## Advisory run

When not in toggle mode:

1. read the current toggle state
2. collect the bounded question and accepted context
3. invoke `$consultant`
4. return the memo

Consultant output remains non-blocking.
