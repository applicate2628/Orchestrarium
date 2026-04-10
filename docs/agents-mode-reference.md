# Agents-Mode Reference

Canonical value-by-value operator reference for the standalone Claude Code pack.

## Provider surface in this branch

| Provider | Canonical file | Legacy fallback | Provider-specific note |
|---|---|---|---|
| Claude Code | `.claude/.agents-mode` | `.claude/.consultant-mode` | `externalProvider: auto` keeps Codex CLI. Explicit values may also select Gemini CLI. Canonical Claude-line config does not include the Claude-target keys `externalClaudeSecretMode` or `externalClaudeProfile`. |

If both files exist, `.claude/.agents-mode` wins. New writes should target `agents-mode`; legacy `consultant-mode` files are fallback-only migration input.

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
| `false` | No default worker preference | Eligible implementer roles may still route to `$external-worker` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external implement adapter | Eligible implementer roles should prefer `$external-worker` as the default routing choice. Risk-sensitive templates or missing external runtime paths may still require rerouting. |

### `preferExternalReviewer`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default reviewer preference | Eligible review or QA roles may still route to `$external-reviewer` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external review adapter | Eligible review and QA roles should prefer `$external-reviewer` as the default routing choice. Mandatory internal reviewers in risk-sensitive templates remain non-replaceable. |

### `externalProvider`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | Use the Claude-line default external provider | Keep Codex CLI as the default external provider for provider-backed consultant or external-adapter work. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. |
| `gemini` | Route provider-backed external work to Gemini CLI | Valid wherever Gemini CLI is installed. |
| `claude` | Invalid on the Claude line | Do not write this value on the Claude line because it collapses into the current provider and creates a self-referential dispatch target. |

## First-write defaults

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` |
|---|---|---|---|---|---|---|
| Claude Code | requested value | `manual` | `auto` | `false` | `false` | `auto` |

## Task continuity

Side requests may refine or temporarily interrupt the current primary task, but they do not replace it unless the user explicitly reprioritizes, cancels, or parks the original task.

After handling a side request, explicitly resume the primary task and state the next concrete step.

An active review or verification task remains non-preemptible by ordinary side clarification unless the user explicitly changes priority.

## Execution continuity

After an accepted phase, continue directly to the next clear phase or verification step unless a real gate blocks progression.

Do not stop only because one local batch of work is complete if the next concrete step is already clear.

`PASS` advances immediately. Pause only on `REVISE`, `BLOCKED`, explicit user reprioritization, or a required human approval point.

## Completion integrity

Before declaring the current task, batch, or closeout complete, reconcile the result against the original user request, the accepted scope, and any still-open required follow-up.

If a concrete required next action is already known and still inside the current task, keep the task open and continue instead of stopping at a partial sub-batch.

When a non-trivial task is interrupted, record a durable resume point: current stage, last accepted artifact, and next concrete step in the owning status surface when available; otherwise state it explicitly in the handoff or closeout.

## Interpretation notes

| Rule | Meaning |
|---|---|
| Explicit user override | An explicit user role or routing request can override the standing toggle state in either direction unless a higher-priority platform or policy rule forbids it. |
| External adapter availability | `$external-worker` and `$external-reviewer` do not silently fall back inside the role. If the external CLI is unavailable, the adapter is disabled and the orchestrator reroutes explicitly. |
| Claude-target keys | `externalClaudeSecretMode` and `externalClaudeProfile` are not part of canonical Claude-line config because Claude-line external dispatch does not target Claude CLI. |
| Unknown keys | Tools that update `.claude/.agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
