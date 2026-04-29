---
name: second-opinion
description: Get an independent second opinion via the consultant role, or manage the Gemini-line consultant toggle state.
---

# Second Opinion

Use this skill to invoke `$consultant` or to change Gemini-line consultant mode.

## Toggle keys

Manage these keys in `.gemini/.agents-mode.yaml`:

- Legacy `.gemini/.agents-mode` is compatibility input only. Resolve Gemini overlay state in this order: local `.gemini/.agents-mode.yaml`, local legacy `.gemini/.agents-mode`, global `~/.gemini/.agents-mode.yaml`, then global legacy `~/.gemini/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.

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

Gemini-line rules:

- `externalProvider: auto` resolves through the active named priority profile, not a Gemini-line default provider
- `externalPriorityProfile` defaults to `balanced`
- `balanced` is the ordinary shipped production profile and keeps `auto` routing on `codex | claude`
- explicit providers are `codex`, `claude`, `gemini`, and `qwen`
- `externalProvider: gemini` is allowed only as an explicit self-provider override for a manual example or compatibility run
- `externalProvider: qwen` is allowed only as an explicit native example or compatibility run
- `externalModelMode` is the shared cross-provider model policy: `runtime-default` leaves the resolved production provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile on the production provider paths
- `externalClaudeApiMode` matters only when provider resolves to Claude
- Gemini is `WEAK MODEL / NOT RECOMMENDED`; shipped and repo-local production `auto` profiles must keep Gemini and Qwen out of provider-order lists
- same-provider Gemini routing must be explicit; ordinary `auto` must still avoid self-bounce
- preserve unknown keys and keep the three new profile/count keys in expanded multi-key form rather than collapsing them into a consultant-only shape
- `parallelMode` is the general helper fan-out rule across internal and external lanes
- `externalOpinionCounts` is lane-specific; when a lane asks for more than one opinion, the lead may invoke the matching external skill repeatedly and aggregate fail closed on top of `parallelMode`

## Toggle actions

- `enable` -> `consultantMode: external`
- `internal` -> `consultantMode: internal`
- `disable` -> `consultantMode: disabled`
- `status` -> read and normalize `.gemini/.agents-mode.yaml`, then print the current resolved values
- If local `.gemini/.agents-mode.yaml` is missing, read local legacy `.gemini/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.gemini/.agents-mode.yaml` and then global legacy `~/.gemini/.agents-mode` before reporting status

Preserve unknown keys on write and normalize comment-free, partial, or older-layout files to the current canonical format on read. Keep one key per line with inline allowed-value comments. Legacy `.gemini/.agents-mode` is compatibility input only and must not be recreated.

## Advisory run

When not in toggle mode:

1. read and normalize the current toggle state
2. collect the bounded question and accepted context
3. invoke `$consultant`
4. return the memo

Consultant output remains non-blocking.
