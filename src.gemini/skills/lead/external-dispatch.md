# Gemini External Dispatch Contract

Shared Gemini-line dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer`.

## Canonical config

- Canonical file: `.gemini/.agents-mode`
- Legacy fallback: `.gemini/.consultant-mode`
- Full operator tables: [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md)

Canonical Gemini-line schema:

```yaml
consultantMode: external  # allowed: external | auto | internal | disabled
delegationMode: manual  # allowed: manual | auto | force
mcpMode: auto  # allowed: auto | force
preferExternalWorker: true  # allowed: false | true
preferExternalReviewer: true  # allowed: false | true
externalProvider: auto  # allowed here: auto | codex | claude
externalClaudeSecretMode: auto  # allowed when Claude is selected: auto | force
```

Rules:

- `externalProvider: auto` keeps provider-backed external dispatch explicit on the Gemini line until a repository or operator selects a concrete external target.
- `externalProvider: codex` selects Codex CLI explicitly.
- `externalProvider: claude` selects Claude CLI explicitly.
- `externalClaudeSecretMode` is valid only when the resolved provider is Claude.
- `externalClaudeProfile` is not part of canonical Gemini-line config.
- Preserve unknown keys on write.
- Keep one key per line with inline allowed-value comments.

## Adapter model

- `$external-worker` is implement-side only.
- `$external-reviewer` is review and QA-side only.
- `$consultant` stays advisory-only.
- The assigned internal role remains provenance metadata only.
- If the selected external CLI is unavailable, the adapter is disabled and the main session reroutes explicitly.
- External adapters do not silently fall back inside the role.

## Provenance header

Every external artifact should record:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <role | none>`
- `Requested provider: <internal | codex | claude>`
- `Resolved provider: <Codex CLI | Claude CLI | none>`
- `Requested consultant mode: <external | auto | internal | disabled>` or `not-applicable`
- `Actual execution path: <external CLI (Codex CLI) | external CLI (Claude CLI) | internal subagent | role disabled>`
- `Model / profile used: <actual model/profile | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | fallback approved by user>`
