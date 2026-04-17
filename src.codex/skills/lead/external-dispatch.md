# External Dispatch Contract

Shared dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer` in the Codex pack.

## Canonical config

The project-local config file is:

- `.agents/.agents-mode.yaml`
- Legacy `.agents/.agents-mode` is compatibility input only. Prefer `.agents/.agents-mode.yaml`, fall back only if it is missing, normalize forward into `.agents/.agents-mode.yaml`, and do not recreate the legacy file.

Full value-by-value operator semantics live in [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md).

Canonical schema:

```yaml
consultantMode: external  # allowed: external | internal | disabled; default: disabled
externalClaudeApiMode: auto  # allowed when Claude is selectable: disabled | auto | force; default: auto
delegationMode: manual  # allowed: manual | auto | force; default: manual
mcpMode: auto  # allowed: auto | force; default: auto
preferExternalWorker: true  # allowed: false | true; default: false
preferExternalReviewer: true  # allowed: false | true; default: false
externalProvider: auto  # allowed here: auto | codex | claude | gemini; default: auto
externalPriorityProfile: balanced  # allowed: balanced | gemini-crosscheck | <repo-local profile>; default: balanced
externalPriorityProfiles: {}  # allowed: structured profile map
externalOpinionCounts: {}  # allowed: structured lane-count map
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalGeminiWorkdirMode: neutral  # allowed: neutral | project
externalGeminiFallbackMode: auto  # allowed when Gemini is selectable: disabled | auto | force; default: auto
externalClaudeProfile: opus-max  # allowed: sonnet-high | opus-max; default: opus-max
```

- `consultantMode` controls `$consultant` behavior.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` routes eligible worker-side roles through `$external-worker` by default.
- `preferExternalReviewer` routes eligible reviewer/QA roles through `$external-reviewer` by default.
- `externalProvider` uses the shared provider universe `auto | codex | claude | gemini`.
- `externalProvider: auto` resolves by lane type through the active priority profile and opinion-count policy below instead of by host-pack identity.
- `externalPriorityProfile` chooses which named routing profile to apply when `externalProvider: auto` is in effect. `balanced` is the quiet default. `gemini-crosscheck` broadens Gemini participation into non-visual advisory and review lanes when multiple independent opinions are requested.
- `externalPriorityProfiles` stores the ordered provider lists for each named profile. The shipped profiles live in the structured block below.
- `externalOpinionCounts` stores how many distinct external opinions each lane should collect. Missing lane entries default to `1`.
- `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each provider-backed external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalModelMode` is the shared cross-provider model-selection policy. `runtime-default` leaves the resolved provider on its runtime default model/profile. `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows only the bounded same-provider fallback used for usage-limit or quota exhaustion while staying inside that provider's approved version floor and lane policy.
- `externalGeminiFallbackMode` controls the explicit Gemini model path only when the resolved provider is Gemini and `externalModelMode: pinned-top-pro` is in effect. `disabled` keeps `gemini-3.1-pro` only, `auto` starts with `gemini-3.1-pro` and allows one limit-triggered retry on `gemini-3-flash`, and `force` starts on `gemini-3-flash` immediately.
- `externalClaudeApiMode` controls whether Claude may use the repo-local secret-backed Claude API path. `disabled` forbids it, `auto` uses it after the allowed Claude CLI path is exhausted, and `force` uses that wrapper-backed path as the first Claude transport. It remains a Claude transport, not a fourth provider.
- Treat named fallback paths as alternate limit or budget pools only when runtime observation shows they exhaust independently. That is repo-local operator policy, not an official provider guarantee.
- `externalClaudeProfile` is Codex-line only and selects or overrides the Claude CLI execution profile when `externalProvider` resolves to Claude. Supported values: `sonnet-high` (`--model sonnet --effort high`) and `opus-max` (`--model opus --effort max`).
- The preference flags are independent.
- Any write to this file must preserve unknown keys and the other known keys.
- Any read of this file for routing must normalize an existing `.agents/.agents-mode.yaml` file to the current canonical format before trusting its flags. Comment-free or older-layout files are valid input, not valid output.
- If `.agents/.agents-mode.yaml` is missing, read legacy `.agents/.agents-mode` as compatibility input only, then normalize either input forward into `.agents/.agents-mode.yaml` before trusting the flags.
- When writing `.agents/.agents-mode.yaml`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- Writes go to `.agents/.agents-mode.yaml`; preserve unknown keys and the other known keys when updating.
- If the file is created from scratch, write the full default shape: the requested `consultantMode`, `externalClaudeApiMode: auto`, `delegationMode: manual`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `externalPriorityProfiles` with shipped `balanced` and `gemini-crosscheck` blocks, `externalOpinionCounts` with documented lanes defaulting to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalGeminiWorkdirMode: neutral`, `externalModelMode: runtime-default`, `externalGeminiFallbackMode: auto`, and `externalClaudeProfile: opus-max` unless the user explicitly requested a different Claude profile.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.

## Routing model

- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions.
- `externalProvider: auto` resolves by lane type through the active profile and opinion-count policy below instead of by host-pack identity.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`; when it is Gemini, honor `externalGeminiWorkdirMode`.
- Explicit user override or repo-local visual-routing heuristics may still choose Gemini over the ordinary `auto` result when the active profile or task domain makes image, icon, or decorative visual work Gemini-first.
- Active profiles may ask for Gemini in non-visual advisory and review lanes when a second or third independent opinion is part of the requested lane policy.
- Explicit `externalProvider: codex` is a self-provider override only. Ordinary `auto` must not silently self-bounce into Codex from the Codex line.
- `externalModelMode: pinned-top-pro` maps the strongest documented provider path as follows: Codex uses `gpt-5.4 --reasoning-effort xhigh`; only `worker.long-autonomous` or another explicitly fully autonomous low-reasoning worker lane may retry once on `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path; Claude uses `opus-max` and then, under `externalClaudeApiMode: auto`, retries through the secret-backed Claude wrapper for CLI/auth/usage-limit or quota-style failure, or starts there immediately when the user explicitly sets `externalClaudeApiMode: force`, instead of downgrading to `sonnet-high`; Gemini uses `gemini-3.1-pro` then follows `externalGeminiFallbackMode` for the allowed same-provider retry.
- Do not silently downgrade below `gpt-5.3-codex-spark` on the Codex line or below Gemini 3 on the Gemini line.
- Treat `gpt-5.3-codex-spark` and `gemini-3-flash` as bounded mechanical overflow paths only. They are acceptable for tightly scoped, low-reasoning, autonomous work, not as the ordinary cheaper mode for broad reasoning or cleanup.
- Treat the secret-backed Claude wrapper differently: repo-local policy accepts it as the economical near-full-strength Claude transport, so `externalClaudeApiMode: force` is an explicit budget choice as well as a limit fallback.
- `externalGeminiFallbackMode: disabled` keeps the Gemini route on `gemini-3.1-pro` only. `externalGeminiFallbackMode: auto` keeps `gemini-3.1-pro` first and allows one fallback retry on `gemini-3-flash` only for quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures. `externalGeminiFallbackMode: force` starts on `gemini-3-flash` immediately and skips the preceding `gemini-3.1-pro` attempt.
- Reserve `externalGeminiFallbackMode: force` for tightly bounded mechanical work. Do not use it as the default path for reasoning-heavy or ambiguous Gemini tasks just to save tokens.
- `externalClaudeApiMode: auto` keeps the installed secret-backed Claude wrapper as the named secondary Claude transport after the allowed Claude CLI path is exhausted. `externalClaudeApiMode: force` starts on that wrapper immediately and skips the preceding Claude CLI attempt.
- When `externalClaudeApiMode` allows the Claude API path, use `.claude/agents/scripts/invoke-claude-api.ps1` from PowerShell or `.claude/agents/scripts/invoke-claude-api.sh` from Bash or Git Bash so the transport reads `SECRET.md`, exports the declared `ANTHROPIC_*` values, and launches plain `claude`. If the wrapper path is requested but unavailable, disclose that as a dependency/config failure.
- If the plain Claude CLI path is selected but is clearly unauthenticated, prefer the allowed Claude API transport instead of repeatedly retrying a plain `claude` command that cannot log in.
- From PowerShell, prefer `.claude/agents/scripts/invoke-claude-api.ps1` when that wrapper surface exists and pass forwarded Claude flags after `--%`. From Bash or Git Bash, prefer `.claude/agents/scripts/invoke-claude-api.sh`, and set `CLAUDE_BIN` explicitly when the active shell PATH differs from the PowerShell PATH.
- On Windows, keep the ordinary external launch path unchanged and try the native Windows shell first. If that native shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- When the resolved provider is Claude and `externalClaudeProfile` is present, honor that profile instead of the shared model policy.
- When the resolved provider is Gemini and the model policy is pinned, honor `externalGeminiFallbackMode`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.
- A spawned internal subagent is still an internal execution path even if the prompt assigns it a provider label such as Gemini Pro. That shape does not satisfy `$external-worker` or `$external-reviewer`.
- The external adapter may be selected by the preference flags or by explicit user / lead override.
- Multiple external adapters may run in parallel when their scopes are independent and the selected provider runtimes support concurrent non-interactive execution.
- Do not cap that fan-out at one instance per helper or provider: the same external helper and the same resolved provider may be launched multiple times concurrently when each run owns a different admitted artifact or disjoint slice.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not forbid brigade-style reuse of the same provider across different independent lanes or slices.
- If the active priority profile requests multiple opinions for a lane, collect them fail-closed: partial collection is evidence, not success, and the lane stays blocked until the requested opinion count is satisfied.
- If internal native slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping those lanes.
- When multiple independent external lanes should launch together, prefer the pack-local `external-brigade` surface so the lead records one bounded brigade plan instead of scattering ad hoc parallel helper launches.
- User override is available in both directions regardless of toggle state.
- Any eligible internal implementer role may be replaced by the best-fit external worker adapter.
- Any eligible reviewer or QA role may be replaced by the best-fit external reviewer adapter.
- `Assigned role` is provenance and routing metadata for the internal role being replaced. It does not narrow the universality of the external adapter.
- QA belongs on the reviewer side.

### `externalPriorityProfiles`

| Profile | Lane | Priority |
| --- | --- | --- |
| `balanced` | `advisory.repo-understanding` | `claude > codex > gemini` |
|  | `advisory.design-adr` | `claude > codex > gemini` |
|  | `review.pre-pr` | `claude > codex > gemini` |
|  | `review.performance-architecture` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.systems-performance-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > codex > gemini` |
|  | `worker.ui-structural-modernization` | `codex > claude > gemini` |
|  | `worker.ui-surgical-patch-cleanup` | `codex > claude > gemini` |
|  | `worker.visual-icon-decorative` | `codex > claude > gemini` |
|  | `review.visual` | `claude > codex > gemini` |
| `gemini-crosscheck` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > gemini > codex` |
|  | `review.pre-pr` | `claude > gemini > codex` |
|  | `review.performance-architecture` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.systems-performance-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > codex > gemini` |
|  | `worker.ui-structural-modernization` | `codex > claude > gemini` |
|  | `worker.ui-surgical-patch-cleanup` | `codex > claude > gemini` |
|  | `worker.visual-icon-decorative` | `codex > claude > gemini` |
|  | `review.visual` | `claude > codex > gemini` |

### `externalOpinionCounts`

| Lane value | Meaning |
| --- | --- |
| omitted or `1` | Single external opinion |
| `2+` | Collect that many distinct external opinions, fail closed if the active profile and available providers cannot satisfy the count |

Rules:

- These counts apply to one lane's opinion requirement, not to general external concurrency.
- The lead may still run multiple same-provider helper instances in parallel for different disjoint brigade items even when the opinion count for each lane is `1`.

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

## Shared lane-priority matrix

| Lane | Priority |
| --- | --- |
| `advisory.repo-understanding` | `claude > codex > gemini` |
| `advisory.design-adr` | `claude > codex > gemini` |
| `review.pre-pr` | `claude > codex > gemini` |
| `review.performance-architecture` | `claude > codex > gemini` |
| `worker.default-implementation` | `codex > claude > gemini` |
| `worker.systems-performance-implementation` | `codex > claude > gemini` |
| `worker.long-autonomous` | `claude > codex > gemini` |
| `worker.ui-structural-modernization` | `codex > claude > gemini` |
| `worker.ui-surgical-patch-cleanup` | `codex > claude > gemini` |
| `worker.visual-icon-decorative` | `codex > claude > gemini` |
| `review.visual` | `claude > codex > gemini` |

Rules:

- `auto` resolves against this matrix, not against the host-pack name.
- Repo-local heuristics may refine the lane choice, but they must not invent a different provider universe.
- Ordinary `auto` must not resolve to the same provider as the current host line.

## Provenance header

Every external or consultant memo/report should record one explicit execution record with these separate fields:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <eligible internal role label | none>`
- `Requested provider: <internal | codex | claude | gemini>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | none>`
- `Requested consultant mode: <external | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

Rules:

- Keep `Execution role` and `Assigned / replaced internal role` on separate lines. Do not merge them into one ambiguous label.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
- For `$external-worker` and `$external-reviewer`, the only valid execution path is the external CLI or a disabled-role outcome.
- `Actual execution path: internal subagent (provider-labeled)` is always invalid for external adapter roles and must be treated as a routing violation, not as partial success.
- If a run is blocked because the provider is unavailable, report that explicitly and let the orchestrator reroute.
