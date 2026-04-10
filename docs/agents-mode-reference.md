# Agents-Mode Reference

Canonical value-by-value operator reference for pack-local `agents-mode` files. Keep full `value | meaning` semantics here and let root manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surfaces

| Provider | Canonical file | Legacy fallback | Provider-specific note |
|---|---|---|---|
| Codex | `.agents/.agents-mode` | `.agents/.consultant-mode` | May also store `externalClaudeProfile` because Codex dispatches externally to Claude CLI |
| Claude Code | `.claude/.agents-mode` | `.claude/.consultant-mode` | Canonical Claude-line config does not include `externalClaudeProfile` because Claude dispatches externally to Codex CLI |

If both files exist on the same provider line, `agents-mode` wins. New writes should target `agents-mode`; legacy `consultant-mode` files are fallback-only migration input.

## Shared keys

### `consultantMode`

| Value | Meaning | Ordinary optional consultant use | Mandatory batch-close external consultant-check |
|---|---|---|---|
| `external` | External-first, no silent fallback | Try the external CLI first. If it is unavailable or fails, disclose the failure and require explicit user approval before falling back to an internal consultant path. | Do not downgrade to internal fallback. Return an unavailable advisory memo and keep the batch open for escalation. |
| `auto` | External-first with silent ordinary fallback | Try the external CLI first. If it is unavailable, fall back to the internal consultant path automatically and disclose the actual execution path in the memo. | Do not silently downgrade. If the external path is unavailable, return an unavailable advisory memo and keep the batch open for escalation. |
| `internal` | Internal-only consultant | Use the internal consultant path for ordinary optional second-opinion work. | Unavailable in this mode because the batch-close check is explicitly external. Keep the batch open for escalation. |
| `disabled` | Consultant disabled | Skip ordinary optional second-opinion use. | Unavailable in this mode. Return an unavailable advisory memo and keep the batch open for escalation. |

Notes:
- No config file behaves like consultant-disabled for ordinary optional consultant use.
- `consultantMode` governs consultant behavior only. It does not replace reviewer, QA, or human publication gates.

### `delegationMode`

| Value | Meaning | Expected behavior |
|---|---|---|
| `manual` | Explicit delegation only | Do not treat ordinary delegation as pre-authorized. Delegate when the user or the governing workflow explicitly requests it. |
| `auto` | Delegation by routing judgment | Treat ordinary delegation as enabled, but still choose locally vs delegated execution based on routing, scope, and specialist fit. |
| `force` | Delegation whenever feasible | Treat delegation as a standing instruction whenever a matching specialist and viable tool path exist. If the tool path is unavailable, say so explicitly instead of pretending the forced delegation happened locally. |

### `mcpMode`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | MCP by judgment | Use relevant MCP tools when they are useful, but do not treat MCP usage as mandatory on every step. |
| `force` | MCP whenever relevant | Treat relevant available MCP usage as an explicit standing instruction rather than an optional convenience. If a relevant MCP is unavailable or broken, disclose that constraint explicitly. |

### `preferExternalWorker`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default worker preference | Eligible implementer roles may still route to `$external-worker` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external implement adapter | Eligible implementer roles should prefer `$external-worker` as the default routing choice. Risk-sensitive templates or missing external runtime paths may still require rerouting. |

### `preferExternalReviewer`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default reviewer preference | Eligible review or QA roles may still route to `$external-reviewer` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external review adapter | Eligible review and QA roles should prefer `$external-reviewer` as the default routing choice. Mandatory internal reviewers in risk-sensitive templates remain non-replaceable. |

## Codex-only key

### `externalClaudeProfile`

| Value | Meaning | Effective Claude CLI mapping |
|---|---|---|
| `sonnet-high` | Balanced Codex-to-Claude external profile | `--model sonnet --effort high` |
| `opus-max` | Maximum-depth Codex-to-Claude external profile | `--model opus --effort max` |

Notes:
- This key is Codex-line only.
- If it appears in Claude-line legacy state, ignore it and do not carry it into canonical Claude-line `agents-mode`.

## First-write defaults

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalClaudeProfile` |
|---|---|---|---|---|---|---|
| Codex | requested value | `manual` | `auto` | `false` | `false` | `sonnet-high` unless explicitly overridden |
| Claude Code | requested value | `manual` | `auto` | `false` | `false` | not part of canonical Claude-line config |

## Interpretation notes

| Rule | Meaning |
|---|---|
| Explicit user override | An explicit user role or routing request can override the standing toggle state in either direction unless a higher-priority platform or policy rule forbids it. |
| External adapter availability | `$external-worker` and `$external-reviewer` do not silently fall back inside the role. If the external CLI is unavailable, the adapter is disabled and the orchestrator reroutes explicitly. |
| Unknown keys | Tools that update `agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
