# Agents-Mode Reference

Canonical value-by-value operator reference for pack-local `agents-mode` files. Keep full `value | meaning` semantics here and let local manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surface in this branch

| Provider | Canonical file | Provider-specific note |
|---|---|---|
| Gemini CLI | `.gemini/.agents-mode` | Optional Orchestrarium overlay for shared routing semantics. Official Gemini runtime config still lives in `.gemini/settings.json`, and the overlay should be initialized after Gemini `/init` rather than treated as a replacement bootstrap. |

## Shared keys

### `consultantMode`

| Value | Meaning | Ordinary optional consultant use | Mandatory batch-close external consultant-check |
|---|---|---|---|
| `external` | External-first, no silent fallback | Try the external CLI first. If it is unavailable or fails, disclose the failure and require explicit user approval before falling back to an internal consultant path. | Do not downgrade to internal fallback. Return an unavailable advisory memo and keep the batch open for escalation. |
| `auto` | External-first with silent ordinary fallback | Try the external CLI first. If it is unavailable, fall back to the internal consultant path automatically and disclose the actual execution path in the memo. | Do not silently downgrade. If the external path is unavailable, return an unavailable advisory memo and keep the batch open for escalation. |
| `internal` | Internal-only consultant | Use the internal consultant path for ordinary optional second-opinion work. | Unavailable in this mode because the batch-close check is explicitly external. Keep the batch open for escalation. |
| `disabled` | Consultant disabled | Skip ordinary optional second-opinion use. | Unavailable in this mode. Return an unavailable advisory memo and keep the batch open for escalation. |

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
| `false` | No default worker preference | Eligible implementer roles may still route to an external worker path when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external implement adapter | Eligible implementer roles should prefer the external worker path as the default routing choice. Risk-sensitive templates or missing external runtime paths may still require rerouting. |

### `preferExternalReviewer`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default reviewer preference | Eligible review or QA roles may still route to an external reviewer path when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external review adapter | Eligible review and QA roles should prefer the external reviewer path as the default routing choice. Mandatory internal reviewers in risk-sensitive templates remain non-replaceable. |

### `externalProvider`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | No standing Gemini default | Gemini keeps provider-backed external dispatch explicit unless a repository adopts a preferred external target. |
| `claude` | Route provider-backed external work to Claude CLI | Valid wherever Claude CLI is installed. When this value is selected, honor `externalClaudeSecretMode`. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. |
| `gemini` | Invalid on the Gemini line | Do not write this value on the Gemini line because it collapses into the current provider and creates a self-referential dispatch target. |

### `externalClaudeSecretMode`

| Value | Meaning | Effective Claude CLI behavior |
|---|---|---|
| `auto` | Limit-triggered SECRET-backed retry | Start with the plain Claude command. If that call fails on quota, limit, or reset errors, rerun the same one-line Claude command once with `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` added to that command environment. |
| `force` | SECRET-backed primary Claude call | Apply the same `ANTHROPIC_*` values from the local Claude `SECRET.md` to the first Claude call immediately. Do not perform a second SECRET-backed retry because the primary call already used that environment override. |

Notes:
- This key is valid on the Gemini line only when `externalProvider` resolves to `claude`.
- `auto` is the first-write default.
- If the required `ANTHROPIC_*` values cannot be read from the local Claude `SECRET.md`, disclose that explicitly. `force` must not silently fall back to a plain Claude call, and `auto` must not claim that the retry happened when it did not.

## First-write defaults

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalClaudeSecretMode` |
|---|---|---|---|---|---|---|---|
| Gemini CLI | requested value | `manual` | `auto` | `false` | `false` | `auto` | `auto` |

## Task continuity

Side requests may refine or temporarily interrupt the current primary task, but they do not replace it unless the user explicitly reprioritizes, cancels, or parks the original task.

After handling a side request, explicitly resume the primary task and state the next concrete step.

An active review or verification task remains non-preemptible by ordinary side clarification unless the user explicitly changes priority.

## Execution continuity

After an accepted phase, continue directly to the next clear phase or verification step unless a real gate blocks progression.

Do not stop only because one local batch of work is complete if the next concrete step is already clear.

`PASS` advances immediately. Pause only on `REVISE`, `BLOCKED`, explicit user reprioritization, or a required human approval point.

## Interpretation notes

| Rule | Meaning |
|---|---|
| Explicit user override | An explicit user role or routing request can override the standing toggle state in either direction unless a higher-priority platform or policy rule forbids it. |
| External adapter availability | External worker and reviewer paths do not silently fall back inside the role. If the selected external CLI is unavailable, the orchestrator must disclose the failure and reroute explicitly. |
| Claude SECRET mode | `externalClaudeSecretMode: auto` keeps the limit-triggered retry path, while `force` applies the same `ANTHROPIC_*` environment to the primary Claude call. Both modes stay on the same provider. |
| Unknown keys | Tools that update `.gemini/.agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it to a consultant-only shape. |
