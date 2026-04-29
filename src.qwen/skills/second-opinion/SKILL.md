---
name: second-opinion
description: Get an independent second opinion via the consultant role, or manage the Qwen-line consultant toggle state.
---

# Second Opinion

Use this skill to invoke `$consultant` or to change Qwen-line consultant mode.

## Toggle keys

Manage these keys in `.qwen/.agents-mode.yaml`:

- Legacy `.qwen/.agents-mode` is compatibility input only. Resolve Qwen overlay state in this order: local `.qwen/.agents-mode.yaml`, local legacy `.qwen/.agents-mode`, global `~/.qwen/.agents-mode.yaml`, then global legacy `~/.qwen/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.

- `consultantMode`
- `delegationMode`
- `parallelMode`
- `mcpMode`
- `preferExternalWorker`
- `preferExternalReviewer`
- `externalProvider`
- `externalPriorityProfile`
- `externalPriorityProfiles`
- `externalOpinionCounts`
- `externalModelMode`
- `externalClaudeApiMode`

Qwen-line rules:

- `externalProvider: auto` resolves through the active named priority profile, not a Qwen-line default provider
- `externalPriorityProfile` defaults to `balanced`
- the shipped `balanced` profile is production-only and keeps `auto` routing on `codex | claude`
- explicit providers are `codex`, `claude`, `gemini`, and `qwen`
- `externalProvider: gemini` and `externalProvider: qwen` are explicit example-only overrides; both are `WEAK MODEL / NOT RECOMMENDED`
- `externalModelMode` is the shared cross-provider model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native production path for the resolved provider
- `externalClaudeApiMode` matters only when provider resolves to Claude
- if a repository wants Qwen participation for a specific example lane, express that through a scalar explicit provider override, not a profile entry
- same-provider Qwen routing must be explicit; ordinary `auto` must still avoid self-bounce
- preserve unknown keys and keep the three new profile/count keys in expanded multi-key form rather than collapsing them into a consultant-only shape
- `parallelMode` is the general helper fan-out rule across internal and external lanes
- `externalOpinionCounts` is lane-specific; when a lane asks for more than one opinion, the lead may invoke the matching external skill repeatedly and aggregate fail closed on top of `parallelMode`

## Toggle actions

- `enable` -> `consultantMode: external`
- `internal` -> `consultantMode: internal`
- `disable` -> `consultantMode: disabled`
- `status` -> read and normalize `.qwen/.agents-mode.yaml`, then print the current resolved values
- If local `.qwen/.agents-mode.yaml` is missing, read local legacy `.qwen/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.qwen/.agents-mode.yaml` and then global legacy `~/.qwen/.agents-mode` before reporting status

Preserve unknown keys on write and normalize comment-free, partial, or older-layout files to the current canonical format on read. Keep one key per line with inline allowed-value comments. Legacy `.qwen/.agents-mode` is compatibility input only and must not be recreated.

## Advisory run

When not in toggle mode:

1. read and normalize the current toggle state
2. collect the bounded question and accepted context
3. invoke `$consultant`
4. return the memo

Consultant output remains non-blocking.
