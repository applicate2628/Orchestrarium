# Agents-Mode Reference

Canonical value-by-value operator reference for pack-local `agents-mode` files. Keep full `value | meaning` semantics here and let root manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surfaces

| Provider | Canonical file | Legacy fallback | Provider-specific note |
|---|---|---|---|
| Codex | `.agents/.agents-mode` | `.agents/.consultant-mode` | `externalProvider: auto` keeps Claude CLI; explicit values may also select Gemini CLI. Codex may additionally store `externalClaudeSecretMode` and `externalClaudeProfile` when the selected provider is Claude |
| Claude Code | `.claude/.agents-mode` | `.claude/.consultant-mode` | `externalProvider: auto` keeps Codex CLI; explicit values may also select Gemini CLI. Canonical Claude-line config does not include the Claude-target keys `externalClaudeSecretMode` or `externalClaudeProfile` |
| Gemini CLI | `.gemini/.agents-mode` | none | Orchestrarium-only operator overlay for shared routing semantics; official Gemini runtime config still lives in `.gemini/settings.json`, and the overlay should be initialized after Gemini `/init` rather than treated as a replacement bootstrap. If Gemini explicitly selects Claude as the external provider, it may also store `externalClaudeSecretMode` |

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

### `externalProvider`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | Use the line default external provider | Codex defaults to Claude CLI, Claude Code defaults to Codex CLI, and Gemini has no standing default external provider until a repository explicitly adopts one. |
| `claude` | Route provider-backed external work to Claude CLI | Valid wherever Claude CLI is installed and the current line is not already Claude-native. When this value is selected, honor `externalClaudeSecretMode`; Codex may additionally honor `externalClaudeProfile`. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed and the current line is not already Codex-native. |
| `gemini` | Route provider-backed external work to Gemini CLI | Valid wherever Gemini CLI is installed and the repository wants Gemini to serve as the external provider for consultant or external-adapter work. |

Notes:
- `externalProvider` selects the external CLI for provider-backed consultant, `$external-worker`, and `$external-reviewer` execution.
- If the selected provider is unavailable, the role does not pretend the same provider-backed run succeeded locally; the orchestrator must disclose the failure and reroute explicitly.
- When the selected provider would collapse into the same provider line, treat that selection as a configuration error and disclose it instead of recursing.

### `externalClaudeSecretMode`

| Value | Meaning | Effective Claude CLI behavior |
|---|---|---|
| `auto` | Limit-triggered SECRET-backed retry | Start with the plain Claude command. If that call fails on quota, limit, or reset errors, rerun the same one-line Claude command once with `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` added to that command environment. |
| `force` | SECRET-backed primary Claude call | Apply the same `ANTHROPIC_*` values from the local Claude `SECRET.md` to the first Claude call immediately. Do not perform a second SECRET-backed retry because the primary call already used that environment override. |

Notes:
- This key is valid on provider lines that may route external work to Claude CLI. In the current pack set that means Codex and Gemini, not Claude Code.
- `auto` is the first-write default where this key exists.
- If the required `ANTHROPIC_*` values cannot be read from the local Claude `SECRET.md`, disclose that explicitly. `force` must not silently fall back to a plain Claude call, and `auto` must not claim that the retry happened when it did not.
- This key changes only the Claude command environment. It does not authorize provider switches or profile downgrades.

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

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalClaudeSecretMode` | `externalClaudeProfile` |
|---|---|---|---|---|---|---|---|---|
| Codex | requested value | `manual` | `auto` | `false` | `false` | `auto` | `auto` | `sonnet-high` unless explicitly overridden |
| Claude Code | requested value | `manual` | `auto` | `false` | `false` | `auto` | not part of canonical Claude-line config | not part of canonical Claude-line config |
| Gemini CLI | requested value | `manual` | `auto` | `false` | `false` | `auto` | `auto` | not part of canonical Gemini-line config |

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
| External adapter availability | `$external-worker` and `$external-reviewer` do not silently fall back inside the role. If the external CLI is unavailable, the adapter is disabled and the orchestrator reroutes explicitly. |
| Claude SECRET mode | `externalClaudeSecretMode: auto` keeps the limit-triggered retry path, while `force` applies the same `ANTHROPIC_*` environment to the primary Claude call. Both modes stay on the same provider and profile. |
| Line-default provider mapping | `externalProvider: auto` preserves current defaults instead of forcing a new provider choice. Codex keeps Claude CLI, Claude keeps Codex CLI, and Gemini stays explicit-only until a repository adopts a preferred external target. |
| Unknown keys | Tools that update `agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
