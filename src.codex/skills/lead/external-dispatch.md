# External Dispatch Contract

Shared dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer` in the Codex pack.

## Canonical config

The project-local config file is now:

- `.agents/.agents-mode`

Legacy fallback:

- `.agents/.consultant-mode`

Full value-by-value operator semantics live in [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md).

Canonical schema:

```yaml
consultantMode: external  # allowed: external | auto | internal | disabled
delegationMode: manual  # allowed: manual | auto | force
mcpMode: auto  # allowed: auto | force
preferExternalWorker: true  # allowed: false | true
preferExternalReviewer: true  # allowed: false | true
externalProvider: auto  # allowed here: auto | claude | gemini
externalClaudeSecretMode: auto  # allowed when Claude is selectable: auto | force
externalClaudeProfile: sonnet-high  # allowed: sonnet-high | opus-max
```

- `consultantMode` controls `$consultant` behavior.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` routes eligible implementer roles through `$external-worker` by default.
- `preferExternalReviewer` routes eligible reviewer/QA roles through `$external-reviewer` by default.
- `externalProvider: auto` preserves the Codex-line default external provider (Claude CLI). Explicit values may select `gemini`, or keep `claude`, for provider-backed consultant or adapter work.
- `externalClaudeSecretMode` controls how Claude receives `ANTHROPIC_*` from the local Claude `SECRET.md` when external work resolves to Claude CLI. `auto` keeps the first call plain and allows one limit-triggered retry; `force` applies the same environment override to the primary call.
- `externalClaudeProfile` is Codex-line only and selects the Claude CLI execution profile when `externalProvider` resolves to Claude. Supported values: `sonnet-high` (`--model sonnet --effort high`) and `opus-max` (`--model opus --effort max`).
- The preference flags are independent.
- Any write to this file must preserve unknown keys and the other known keys.
- When writing `.agents/.agents-mode`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- If both files exist, `.agents/.agents-mode` wins.
- If only the legacy file exists, treat legacy `mode` as `consultantMode`, default missing `delegationMode` to `manual`, default missing `mcpMode` to `auto`, default missing `externalClaudeSecretMode` to `auto`, and preserve any existing `preferExternalWorker`, `preferExternalReviewer`, `externalProvider`, and `externalClaudeProfile` values during migration.
- New writes go to `.agents/.agents-mode`; do not create new `.consultant-mode` files.
- If the file is created from scratch, write the full default shape: the requested `consultantMode`, `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalClaudeSecretMode: auto`, and `externalClaudeProfile: sonnet-high` unless the user explicitly requested a different Claude profile.

## Routing model

- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions.
- On the Codex pack, `externalProvider: auto` means Claude CLI and should honor `externalClaudeSecretMode`; when `externalClaudeProfile` is present, honor that too.
- Codex may also select Gemini CLI explicitly via `externalProvider: gemini`.
- `externalClaudeSecretMode: auto` keeps the first Claude call plain and allows one SECRET-backed one-line retry only for limit, quota, or reset failures on the selected Claude provider. Do not use it to mask auth failures, bad prompts, or unrelated CLI errors.
- `externalClaudeSecretMode: force` applies `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` to the primary Claude call immediately. If those values cannot be read, disclose a dependency/config failure instead of silently dropping back to a plain Claude call.
- The Claude pack mirrors this contract with Codex CLI.
- The external adapter may be selected by the preference flags or by explicit user / lead override.
- User override is available in both directions regardless of toggle state.
- Any eligible internal implementer role may be replaced by the best-fit external worker adapter.
- Any eligible reviewer or QA role may be replaced by the best-fit external reviewer adapter.
- `Assigned role` is provenance and routing metadata for the internal role being replaced. It does not narrow the universality of the external adapter.
- QA belongs on the reviewer side.

## Role behavior

- `$consultant` stays advisory-only and continues to use the `consultantMode` field.
- `$external-worker` is implement-only.
- `$external-reviewer` covers review and QA on the reviewer side.
- If the external CLI is unavailable for either external role, that role is disabled at the role level and the orchestrator may reroute to another eligible internal specialist.
- There is no internal fallback inside the external role itself.

## Provider matrix

| Pack | `externalProvider: auto` | Explicit alternates |
| --- | --- | --- |
| Codex | Claude CLI | Gemini CLI |
| Claude Code | Codex CLI | Gemini CLI |
| Gemini CLI | none | Codex CLI or Claude CLI when a repository explicitly enables Gemini-side external dispatch |

## Provenance header

Every external or consultant memo/report should record one explicit execution record with these separate fields:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <eligible internal role label | none>`
- `Requested provider: <internal | claude | gemini>`
- `Resolved provider: <Claude CLI | Gemini CLI | none>`
- `Requested consultant mode: <external | auto | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Claude CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

Rules:

- Keep `Execution role` and `Assigned / replaced internal role` on separate lines. Do not merge them into one ambiguous label.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- For `$external-worker` and `$external-reviewer`, the only valid execution path is the external CLI or a disabled-role outcome.
- If a run is blocked because the provider is unavailable, report that explicitly and let the orchestrator reroute.
