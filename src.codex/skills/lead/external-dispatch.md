# External Dispatch Contract

Shared dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer` in the Codex pack.

## Canonical config

The project-local config file is now:

- `.agents/.agents-mode`

Legacy fallback:

- `.agents/.consultant-mode`

Treat the inline schema in this contract as the canonical operator reference for this standalone Codex branch.

Canonical schema:

```yaml
consultantMode: external  # allowed: external | auto | internal | disabled
delegationMode: manual  # allowed: manual | auto | force
mcpMode: auto  # allowed: auto | force
preferExternalWorker: true  # allowed: false | true
preferExternalReviewer: true  # allowed: false | true
externalProvider: auto  # allowed here: auto | claude | gemini
externalClaudeProfile: sonnet-high  # allowed: sonnet-high | opus-max
```

- `consultantMode` controls `$consultant` behavior.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` routes eligible implementer roles through `$external-worker` by default.
- `preferExternalReviewer` routes eligible reviewer/QA roles through `$external-reviewer` by default.
- `externalProvider: auto` preserves the Codex-line default external provider (Claude CLI). Explicit values may select `gemini`, or keep `claude`, for provider-backed consultant or adapter work.
- `externalClaudeProfile` is Codex-line only and selects the Claude CLI execution profile when `externalProvider` resolves to Claude. Supported values: `sonnet-high` (`--model sonnet --effort high`) and `opus-max` (`--model opus --effort max`).
- The preference flags are independent.
- Any write to this file must preserve unknown keys and the other known keys.
- When writing `.agents/.agents-mode`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- If both files exist, `.agents/.agents-mode` wins.
- If only the legacy file exists, treat legacy `mode` as `consultantMode`, default missing `delegationMode` to `manual`, default missing `mcpMode` to `auto`, and preserve any existing `preferExternalWorker`, `preferExternalReviewer`, and `externalClaudeProfile` values during migration.
- New writes go to `.agents/.agents-mode`; do not create new `.consultant-mode` files.
- If the file is created from scratch, write the full default shape: the requested `consultantMode`, `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, and `externalClaudeProfile: sonnet-high` unless the user explicitly requested a different Claude profile.

## Routing model

- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions.
- On the Codex pack, `externalProvider: auto` means Claude CLI and should honor `externalClaudeProfile` when that key is present.
- Codex may also select Gemini CLI explicitly via `externalProvider: gemini`.
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

Every external or consultant memo/report should record:

- `Requested consultant mode`
- `Actual execution path`
- `Deviation reason`

For the external roles, the only valid execution path is the external CLI or a disabled-role outcome. If a run is blocked because the provider is unavailable, the role should report that explicitly and let the orchestrator reroute.
