# External Dispatch Contract

Shared dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer` in the Codex pack.

## Canonical config

The project-local toggle file remains:

- `.agents/.consultant-mode`

Extended schema:

```yaml
mode: external
preferExternalWorker: true
preferExternalReviewer: true
```

- `mode` controls `$consultant` behavior and remains backward compatible.
- `preferExternalWorker` routes eligible implementer roles through `$external-worker` by default.
- `preferExternalReviewer` routes eligible reviewer/QA roles through `$external-reviewer` by default.
- The preference flags are independent.
- Any write to this file must preserve the other keys.
- If the file is created from scratch, write all three keys with `preferExternalWorker: false` and `preferExternalReviewer: false` unless the user explicitly requested a different preference.

## Routing model

- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions.
- On the Codex pack, external dispatch goes to Claude CLI.
- The Claude pack mirrors this contract with Codex CLI.
- The external adapter may be selected by the preference flags or by explicit user / lead override.
- User override is available in both directions regardless of toggle state.
- Any eligible internal implementer role may be replaced by the best-fit external worker adapter.
- Any eligible reviewer or QA role may be replaced by the best-fit external reviewer adapter.
- `Assigned role` is provenance and routing metadata for the internal role being replaced. It does not narrow the universality of the external adapter.
- QA belongs on the reviewer side.

## Role behavior

- `$consultant` stays advisory-only and continues to use the `mode` field.
- `$external-worker` is implement-only.
- `$external-reviewer` covers review and QA on the reviewer side.
- If the external CLI is unavailable for either external role, that role is disabled at the role level and the orchestrator may reroute to another eligible internal specialist.
- There is no internal fallback inside the external role itself.

## Provider matrix

| Pack | External provider |
| --- | --- |
| Codex | Claude CLI |
| Claude Code | Codex CLI |

## Provenance header

Every external or consultant memo/report should record:

- `Requested mode`
- `Actual execution path`
- `Deviation reason`

For the external roles, the only valid execution path is the external CLI or a disabled-role outcome. If a run is blocked because the provider is unavailable, the role should report that explicitly and let the orchestrator reroute.
