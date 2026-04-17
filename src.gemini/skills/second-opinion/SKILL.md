---
name: second-opinion
description: Get an independent second opinion via the consultant role, or manage the Gemini-line consultant toggle state.
---

# Second Opinion

Use this skill to invoke `$consultant` or to change Gemini-line consultant mode.

## Toggle keys

Manage these keys in `.gemini/.agents-mode.yaml`:

- Legacy `.gemini/.agents-mode` is compatibility input only. Prefer `.gemini/.agents-mode.yaml`, fall back only if it is missing, normalize forward into `.gemini/.agents-mode.yaml`, and do not recreate the legacy file.

- `consultantMode`
- `delegationMode`
- `mcpMode`
- `preferExternalWorker`
- `preferExternalReviewer`
- `externalProvider`
- `externalPriorityProfile`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalGeminiFallbackMode`
- `externalClaudeApiMode`

Gemini-line rules:

- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider
- `externalPriorityProfile` defaults to `balanced`
- `balanced` is the ordinary profile; `gemini-crosscheck` is the profile that intentionally keeps Gemini in the non-visual advisory and review cross-check set
- explicit providers are `codex`, `claude`, and `gemini`
- `externalProvider: gemini` is allowed only as an explicit self-provider override
- `externalModelMode` is the shared cross-provider model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion
- `externalGeminiFallbackMode` matters only when provider resolves to Gemini and the model policy is pinned
- Under `externalModelMode: pinned-top-pro`, `externalGeminiFallbackMode: auto` keeps `gemini-3.1-pro` first and allows one retry on `gemini-3-flash` only for quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures
- `externalClaudeApiMode` matters only when provider resolves to Claude
- documented repo-local visual heuristics may still keep eligible image/icon/decorative visual lanes on Gemini itself when that routing remains honest
- same-provider Gemini routing must be explicit; ordinary `auto` must still avoid self-bounce
- preserve unknown keys and keep the three new profile/count keys in expanded multi-key form rather than collapsing them into a consultant-only shape
- `externalOpinionCounts` is lane-specific; when a lane asks for more than one opinion, the lead may invoke the matching external skill repeatedly and aggregate fail closed

## Toggle actions

- `enable` -> `consultantMode: external`
- `internal` -> `consultantMode: internal`
- `disable` -> `consultantMode: disabled`
- `status` -> read and normalize `.gemini/.agents-mode.yaml`, then print the current resolved values
- If the canonical file is missing, read legacy `.gemini/.agents-mode` as compatibility input only and normalize it forward into `.gemini/.agents-mode.yaml` before reporting status

Preserve unknown keys on write and normalize comment-free, partial, or older-layout files to the current canonical format on read. Keep one key per line with inline allowed-value comments. Legacy `.gemini/.agents-mode` is compatibility input only and must not be recreated.

## Advisory run

When not in toggle mode:

1. read and normalize the current toggle state
2. collect the bounded question and accepted context
3. invoke `$consultant`
4. return the memo

Consultant output remains non-blocking.
