# External Dispatch Contract

Shared dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer` in the Codex pack.

## Canonical config

The project-local config file is:

- `.agents/.agents-mode`

Full value-by-value operator semantics live in [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md).

Canonical schema:

```yaml
consultantMode: external  # allowed: external | internal | disabled
delegationMode: manual  # allowed: manual | auto | force
mcpMode: auto  # allowed: auto | force
preferExternalWorker: true  # allowed: false | true
preferExternalReviewer: true  # allowed: false | true
externalProvider: auto  # allowed here: auto | codex | claude | gemini
externalPriorityProfile: balanced  # allowed: balanced | gemini-crosscheck | <repo-local profile>
externalPriorityProfiles: {}  # allowed: structured profile map
externalOpinionCounts: {}  # allowed: structured lane-count map
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalGeminiWorkdirMode: neutral  # allowed: neutral | project
externalClaudeSecretMode: auto  # allowed when Claude is selectable: auto | force
externalClaudeApiMode: auto  # allowed when Claude is selectable: disabled | auto | force
externalClaudeProfile: sonnet-high  # allowed: sonnet-high | opus-max
```

- `consultantMode` controls `$consultant` behavior.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` routes eligible worker-side roles through `$external-worker` by default.
- `preferExternalReviewer` routes eligible reviewer/QA roles through `$external-reviewer` by default.
- `externalProvider: auto` resolves by the active priority profile and opinion-count policy below instead of by host-pack identity.
- `externalPriorityProfile` chooses which named routing profile to apply when `externalProvider: auto` is in effect. `balanced` is the quiet default. `gemini-crosscheck` broadens Gemini participation into non-visual advisory and review lanes when multiple independent opinions are requested.
- `externalPriorityProfiles` stores the ordered provider lists for each named profile. The shipped profiles live in the structured block below.
- `externalOpinionCounts` stores how many distinct external opinions each lane should collect. Missing lane entries default to `1`.
- `externalOpinionCounts` is a same-lane distinct-opinion policy, not a concurrency cap. It does not limit how many same-provider brigade items may run in parallel across disjoint lanes or slices.
- `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each provider-backed external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalClaudeSecretMode` controls how Claude receives `ANTHROPIC_*` from the local Claude `SECRET.md` when external work resolves to Claude CLI. `auto` keeps the first call plain and allows one limit-triggered retry; `force` applies the same environment override to the primary call.
- `externalClaudeApiMode` controls whether Claude may use the repo-local `claude-api` transport. `disabled` forbids it, `auto` uses it after the allowed Claude CLI path is exhausted, and `force` uses `claude-api` as the first Claude transport.
- `externalClaudeProfile` is Codex-line only and selects the Claude CLI execution profile when `externalProvider` resolves to Claude. Supported values: `sonnet-high` (`--model sonnet --effort high`) and `opus-max` (`--model opus --effort max`).
- The preference flags are independent.
- Any write to this file must preserve unknown keys and the other known keys.
- Any read of this file for routing must normalize an existing `.agents/.agents-mode` file to the current canonical format before trusting its flags. Comment-free or older-layout files are valid input, not valid output.
- When writing `.agents/.agents-mode`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- Writes go to `.agents/.agents-mode`; preserve unknown keys and the other known keys when updating.
- If the file is created from scratch, write the full default shape: the requested `consultantMode`, `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `externalPriorityProfiles` with shipped `balanced` and `gemini-crosscheck` blocks, `externalOpinionCounts` with documented lanes defaulting to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalGeminiWorkdirMode: neutral`, `externalClaudeSecretMode: auto`, `externalClaudeApiMode: auto`, and `externalClaudeProfile: sonnet-high` unless the user explicitly requested a different Claude profile.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.

## Routing model

- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions.
- On the Codex pack, `externalProvider: auto` resolves through the active priority profile and opinion-count policy, then applies the explicit-only self-provider rule and CLI availability.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`; when it is Gemini, honor `externalGeminiWorkdirMode`.
- Explicit user override or repo-local visual-routing heuristics may still choose Gemini over the ordinary `auto` result when the active profile or task domain makes image, icon, or decorative visual work Gemini-first.
- Active profiles may ask for Gemini in non-visual advisory and review lanes when a second or third independent opinion is part of the requested lane policy.
- Codex may also select Codex, Claude, or Gemini CLI explicitly via `externalProvider: codex`, `externalProvider: claude`, or `externalProvider: gemini`.
- `externalClaudeSecretMode: auto` keeps the first Claude call plain and allows one SECRET-backed one-line retry only for limit, quota, or reset failures on the selected Claude provider. Do not use it to mask auth failures, bad prompts, or unrelated CLI errors.
- `externalClaudeSecretMode: force` applies `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` to the primary Claude call immediately. If those values cannot be read, disclose a dependency/config failure instead of silently dropping back to a plain Claude call.
- `externalClaudeApiMode: auto` keeps `claude-api` as the named secondary Claude transport after the allowed Claude CLI path is exhausted. `externalClaudeApiMode: force` starts on `claude-api` immediately and skips the preceding Claude CLI attempt.
- When `externalClaudeApiMode` allows `claude-api`, use the local `claude-api` command if it is available on PATH. If the transport is requested but unavailable, disclose that as a dependency/config failure.
- The Claude pack mirrors this contract with Codex CLI.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.
- The external adapter may be selected by the preference flags or by explicit user / lead override.
- Multiple external adapters may run in parallel when their scopes are independent and the selected provider runtimes support concurrent non-interactive execution.
- If the active priority profile requests multiple opinions for a lane, collect them fail-closed: partial collection is evidence, not success, and the lane stays blocked until the requested opinion count is satisfied.
- If internal native slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping those lanes.
- Same-provider fan-out is allowed for disjoint admitted artifacts and slices; multiple parallel helper items may target the same provider when they are genuinely independent.
- When a bounded batch of helper items needs to be launched and aggregated together, prefer the repo-local external-brigade utility over ad hoc fan-out in chat notes.
- User override is available in both directions regardless of toggle state.
- Any eligible internal implementer role may be replaced by the best-fit external worker adapter.
- Any eligible reviewer or QA role may be replaced by the best-fit external reviewer adapter.
- `Assigned role` is provenance and routing metadata for the internal role being replaced. It does not narrow the universality of the external adapter.
- QA belongs on the reviewer side.

### `externalPriorityProfiles`

| Profile | Lane | Priority |
| --- | --- | --- |
| `balanced` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > codex > gemini` |
|  | `review.pre-pr` | `claude > codex > gemini` |
|  | `review.performance-architecture` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.systems-performance-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > codex > gemini` |
|  | `worker.ui-structural-modernization` | `gemini > claude > codex` |
|  | `worker.ui-surgical-patch-cleanup` | `claude > codex > gemini` |
|  | `worker.visual-icon-decorative` | `gemini > claude > codex` |
|  | `review.visual` | `gemini > claude > codex` |
| `gemini-crosscheck` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > gemini > codex` |
|  | `review.pre-pr` | `claude > gemini > codex` |
|  | `review.performance-architecture` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.systems-performance-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > gemini > codex` |
|  | `worker.ui-structural-modernization` | `gemini > claude > codex` |
|  | `worker.ui-surgical-patch-cleanup` | `claude > codex > gemini` |
|  | `worker.visual-icon-decorative` | `gemini > claude > codex` |
|  | `review.visual` | `gemini > claude > codex` |

### `externalOpinionCounts`

| Lane value | Meaning |
| --- | --- |
| omitted or `1` | Single external opinion |
| `2+` | Collect that many distinct external opinions, fail closed if the active profile and available providers cannot satisfy the count |

## Role behavior

- `$consultant` stays advisory-only and continues to use the `consultantMode` field.
- `$external-worker` covers the full worker-side lane.
- `$external-reviewer` covers review and QA on the reviewer side.
- If the external CLI is unavailable for either external role, that role is disabled at the role level and the orchestrator may reroute to another eligible internal specialist.
- There is no internal fallback inside the external role itself.

## Eligibility gate

Resolve external dispatch in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Required result |
| --- | --- | --- |
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker or review lane. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the work as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the work as review or QA. |
| Owner roles such as `$product-manager` or `$lead` | unsupported | Fail fast before provider resolution. There is no generic external owner adapter in the Codex pack. |

Rules:

- An explicit request for `external` does not create a new adapter type.
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing Claude or Gemini availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution.

## Named priority profiles

| Lane | Priority |
| --- | --- |
| `advisory.repo-understanding` | `claude > gemini > codex` |
| `advisory.design-adr` | `claude > codex > gemini` |
| `review.pre-pr` | `claude > codex > gemini` |
| `review.performance-architecture` | `claude > codex > gemini` |
| `worker.default-implementation` | `codex > claude > gemini` |
| `worker.systems-performance-implementation` | `codex > claude > gemini` |
| `worker.long-autonomous` | `claude > codex > gemini` |
| `worker.ui-structural-modernization` | `gemini > claude > codex` |
| `worker.ui-surgical-patch-cleanup` | `claude > codex > gemini` |
| `worker.visual-icon-decorative` | `gemini > claude > codex` |
| `review.visual` | `gemini > claude > codex` |

## Provenance header

Every external or consultant memo/report should record one explicit execution record with these separate fields:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <eligible internal role label | none>`
- `Requested provider: <internal | codex | claude | gemini>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | none>`
- `Requested consultant mode: <external | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Claude CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

Rules:

- Keep `Execution role` and `Assigned / replaced internal role` on separate lines. Do not merge them into one ambiguous label.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
- `auto` resolves by lane type through the active priority profile, then applies the explicit-only self-provider rule and CLI availability. The host pack does not redefine the provider universe.
- For `$external-worker` and `$external-reviewer`, the only valid execution path is the external CLI or a disabled-role outcome.
- If a run is blocked because the provider is unavailable, report that explicitly and let the orchestrator reroute.
