# External Dispatch Contract

This contract defines the shared Claude-line routing semantics for the consultant toggle file and the external adapters.

## Shared config file

- Canonical path: `.claude/.agents-mode`
- Legacy fallback: `.claude/.consultant-mode`
- Existing consultant workflows continue to work through legacy fallback, but new writes should target `.claude/.agents-mode`.
- Full value-by-value operator semantics live in [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md).

Supported canonical keys:

```yaml
consultantMode: external  # allowed: external | auto | internal | disabled
delegationMode: manual  # allowed: manual | auto | force
mcpMode: auto  # allowed: auto | force
preferExternalWorker: true  # allowed: false | true
preferExternalReviewer: true  # allowed: false | true
externalProvider: auto  # allowed here: auto | codex | gemini
```

Semantics:

- `consultantMode` continues to govern `$consultant`.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` and `preferExternalReviewer` are routing preferences for eligible external adapter substitutions.
- `externalProvider: auto` preserves the Claude-line default external provider (Codex CLI). Explicit values may select `gemini`, or keep `codex`, for provider-backed consultant or adapter work.
- Claude-line no longer treats `externalClaudeProfile` as part of the canonical schema; if it appears in a legacy `.consultant-mode` file, ignore it for Claude-line execution and do not write it into the new `.agents-mode` file during migration.
- Any tool that updates the file must preserve unknown keys in place and must not rewrite the file back to a consultant-only shape.
- When writing `.claude/.agents-mode`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- If both files exist, `.claude/.agents-mode` wins.

## Claude-line provider

- `externalProvider: auto` keeps Claude-line external adapters on Codex CLI.
- Claude-line may also select Gemini CLI explicitly via `externalProvider: gemini`.
- The adapter does not change the team template JSON.
- The adapter replaces an eligible internal role at routing time and keeps the replaced role label in provenance.
- If the external CLI is unavailable, the adapter is disabled and the orchestrator may reroute the work to another eligible path.
- The adapter itself must not silently fall back to an internal specialist.

## External worker

- `$external-worker` is the external implementation adapter.
- It may stand in for any eligible implement-side role.
- The `Assigned role` provenance label names the internal implementer role being replaced.
- Implementation-side tasks stay implementation-side; the adapter does not take review or QA ownership.

## External reviewer

- `$external-reviewer` is the external review-side adapter.
- It may stand in for any eligible review or QA-side role.
- The `Assigned role` provenance label names the internal review-side role being replaced.
- Review-side tasks stay review-side; the adapter does not take implementation ownership.
- Mandatory internal gates in security-sensitive and performance-sensitive templates remain non-replaceable.

## Provenance header

Every external-adapter artifact should include one explicit execution record with these separate fields:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <eligible internal role label | none>`
- `Requested provider: <internal | codex | gemini>`
- `Resolved provider: <Codex CLI | Gemini CLI | none>`
- `Requested consultant mode: <external | auto | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <external CLI (Codex CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | fallback approved by user>`

Rules:

- Keep `Execution role` and `Assigned / replaced internal role` on separate lines. Do not merge them into one ambiguous label.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- The adapter may replace an internal role for provenance, but the artifact must still show which role actually ran and which role was replaced.
