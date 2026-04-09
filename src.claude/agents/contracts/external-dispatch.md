# External Dispatch Contract

This contract defines the shared Claude-line routing semantics for the consultant toggle file and the external adapters.

## Shared config file

- Path: `.claude/.consultant-mode`
- File name stays unchanged for backward compatibility.
- The schema is additive. Existing `mode` workflows continue to work.

Supported keys:

- `mode: external | auto | internal | disabled`
- `preferExternalWorker: true | false`
- `preferExternalReviewer: true | false`

Semantics:

- `mode` continues to govern `$consultant`.
- `preferExternalWorker` and `preferExternalReviewer` are routing preferences for eligible external adapter substitutions.
- Any tool that updates the file must preserve unknown keys and must not rewrite the file back to a mode-only shape.

## Claude-line provider

- Claude-line external adapters dispatch to Codex CLI.
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

Every external-adapter artifact should include a provenance header with:

- `Requested mode: <external | auto | internal>`
- `Preferred adapter: <worker | reviewer | none>`
- `Assigned role: <eligible internal role label>`
- `Actual execution path: <external CLI (Codex) | role disabled>`
- `Deviation reason: <none | external unavailable: [reason] | fallback approved by user>`
