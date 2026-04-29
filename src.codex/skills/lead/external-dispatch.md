# External Dispatch Contract

Shared dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer` in the Codex pack.

## Canonical config

The project-local config file is:

- `.agents/.agents-mode.yaml`
- Legacy `.agents/.agents-mode` is compatibility input only. Resolve Codex overlay state in this order: local `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, global `~/.codex/.agents-mode.yaml`, then global legacy `~/.codex/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.

Full value-by-value operator semantics live in [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md).

Canonical schema:

```yaml
consultantMode: external  # allowed: external | internal | disabled; default: disabled
externalClaudeApiMode: auto  # controls advisory/review-only claude-secret candidate: disabled | auto | force; default: auto
delegationMode: manual  # allowed: manual | auto | force; default: manual
parallelMode: auto  # allowed: manual | auto | force; default: auto
mcpMode: auto  # allowed: auto | force; default: auto
preferExternalWorker: true  # allowed: false | true; default: false
preferExternalReviewer: true  # allowed: false | true; default: false
externalProvider: auto  # allowed here: auto | codex | claude | gemini | qwen; default: auto; gemini/qwen are explicit example-only and not recommended for shipped auto
externalPriorityProfile: balanced  # allowed: balanced | <repo-local production profile>; default: balanced
externalPriorityProfiles: {}  # allowed: structured profile map
externalOpinionCounts: {}  # allowed: structured lane-count map
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalModelMode: runtime-default  # allowed: runtime-default | pinned-top-pro; default: runtime-default
externalClaudeProfile: opus-max  # allowed: sonnet-high | opus-max; default: opus-max
```

- `consultantMode` controls `$consultant` behavior.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `parallelMode: manual` keeps ordinary parallel fan-out explicit-only, `auto` parallelizes safe independent lanes by routing judgment, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` routes eligible worker-side roles through `$external-worker` by default.
- `preferExternalReviewer` routes eligible reviewer/QA roles through `$external-reviewer` by default.
- `externalProvider` uses the shared provider universe `auto | codex | claude | gemini | qwen`.
- `externalProvider: auto` resolves by lane type through the active production priority profile and opinion-count policy below instead of by host-pack identity. Ordinary `auto` must not silently self-bounce into the Codex line and must not select example-only providers.
- `externalPriorityProfile` chooses which named production routing profile to apply when `externalProvider: auto` is in effect. `balanced` is the quiet default. Repo-local custom profiles must keep example-only providers out of production `auto`.
- `externalPriorityProfiles` stores the ordered provider lists for each named profile. The shipped profiles live in the structured block below.
- `externalOpinionCounts` stores how many distinct external opinions each lane should collect. Missing lane entries default to `1`.
- `externalCodexWorkdirMode` and `externalClaudeWorkdirMode` choose whether each production-provider external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalModelMode` is the shared cross-provider model-selection policy. `runtime-default` leaves the resolved provider on its runtime default model/profile. `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows only the bounded same-provider fallback used for usage-limit or quota exhaustion while staying inside that provider's approved version floor and lane policy.
- `externalClaudeApiMode` controls whether the repo-local secret-backed Claude wrapper may appear as the supplemental `claude-secret` candidate in advisory and review profile orders. `disabled` removes it, `auto` allows it only when an advisory or review order reaches `claude-secret` after primary `claude`/`codex`, and `force` keeps that supplemental candidate available for advisory/review even when plain Claude is unavailable. It is independent of the primary `claude` candidate, not a scalar provider, and not an implementation or editing fallback.
- Treat named fallback paths as alternate limit or budget pools only when runtime observation shows they exhaust independently. That is repo-local operator policy, not an official provider guarantee.
- `externalClaudeProfile` is Codex-line only and selects or overrides the Claude CLI execution profile when `externalProvider` resolves to Claude. Supported values: `sonnet-high` (`--model sonnet --effort high`) and `opus-max` (`--model opus --effort max`).
- The preference flags are independent.
- Any write to this file must preserve unknown keys and the other known keys.
- Any read of this file for routing must normalize the effective Codex overlay file to the current canonical format before trusting its flags. Comment-free or older-layout files are valid input, not valid output.
- If local `.agents/.agents-mode.yaml` is missing, read local legacy `.agents/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.codex/.agents-mode.yaml` and then global legacy `~/.codex/.agents-mode`. Normalize whichever file supplied the effective config in place before trusting the flags.
- When writing `.agents/.agents-mode.yaml`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- Writes go to `.agents/.agents-mode.yaml`; preserve unknown keys and the other known keys when updating.
- If the file is created from scratch, write the full default shape: the requested `consultantMode`, `externalClaudeApiMode: auto`, `delegationMode: manual`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `externalPriorityProfiles` with the shipped `balanced` block, `externalOpinionCounts` with documented lanes defaulting to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalModelMode: runtime-default`, and `externalClaudeProfile: opus-max` unless the user explicitly requested a different Claude profile.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.

## Routing model

- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions.
- `externalProvider: auto` resolves by lane type through the active production profile and opinion-count policy below instead of by host-pack identity.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`.
- Explicit user override or documented repo-local heuristics may still choose an explicit example-only provider route such as Qwen, or the weaker/not-recommended Gemini path, for demonstration or compatibility work. Shipped production `auto` does not do that.
- Explicit `externalProvider: codex` is a self-provider override only. Ordinary `auto` must not silently self-bounce into Codex from the Codex line.
- `externalModelMode: pinned-top-pro` maps the strongest documented production-provider path as follows: Codex uses `gpt-5.4 --reasoning-effort xhigh`; only `worker.long-autonomous` or another explicitly fully autonomous low-reasoning worker lane may retry once on `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path; Claude uses `opus-max` on the primary `claude` candidate instead of downgrading to `sonnet-high`. The secret-backed Claude wrapper is separate: it is exposed only as `claude-secret` in advisory/review profile orders after primary `claude`/`codex`, never as a retry or transport swap for the primary `claude` candidate. Example-only Gemini and Qwen routes stay explicit/manual and do not add separate production fallback keys to this schema.
- Do not silently downgrade below `gpt-5.3-codex-spark` on the Codex line.
- Treat `gpt-5.3-codex-spark` as a bounded mechanical overflow path only. It is acceptable for tightly scoped, low-reasoning, autonomous work, not as the ordinary cheaper mode for broad reasoning or cleanup.
- Treat the secret-backed Claude wrapper differently: repo-local policy accepts it only as the weaker supplemental `claude-secret` advisory/review candidate. `externalClaudeApiMode: force` is an explicit advisory/review availability choice, not permission to run implementation, worker-side execution, or editing work through the wrapper.
- `externalClaudeApiMode: auto` allows `claude-secret` only when an advisory or review profile order reaches it after primary `claude`/`codex`. `externalClaudeApiMode: force` keeps `claude-secret` available for advisory/review lanes, but it still does not skip earlier primary profile candidates.
- When an advisory or review route resolves to `claude-secret`, use `.claude/agents/scripts/invoke-claude-api.ps1` from PowerShell or `.claude/agents/scripts/invoke-claude-api.sh` from Bash or Git Bash so the transport reads `SECRET.md`, exports the declared `ANTHROPIC_*` values, and launches plain `claude`. If the wrapper path is requested but unavailable, disclose that as a dependency/config failure.
- If the plain Claude CLI path is selected and fails, do not silently convert that same primary `claude` run to the wrapper. Advisory/review lanes may later collect `claude-secret` as a separate profile candidate when enabled; worker or mutating routes must report Claude unavailable or reroute honestly.
- From PowerShell, use `.claude/agents/scripts/invoke-claude-api.ps1` only for a resolved `claude-secret` advisory/review candidate and pass forwarded Claude flags after `--%`. From Bash or Git Bash, use `.claude/agents/scripts/invoke-claude-api.sh`, and set `CLAUDE_BIN` explicitly when the active shell PATH differs from the PowerShell PATH.
- On Windows, keep the ordinary external launch path unchanged and try the native Windows shell first. If that native shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- External CLI launches that carry a substantive task prompt must use file-based prompt delivery: write the prompt to a temporary prompt file and feed it through the provider's stdin or supported file-input mechanism. Keep command-line arguments limited to launcher flags, model/profile options, and file paths; inline prompt argv is allowed only for tiny smoke checks or a documented provider limitation, and record that deviation in the execution artifact.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- When the resolved provider is Claude and `externalClaudeProfile` is present, honor that profile instead of the shared model policy.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.
- A spawned internal subagent is still an internal execution path even if the prompt assigns it a provider label such as Gemini Pro. That shape does not satisfy `$external-worker` or `$external-reviewer`.
- The external adapter may be selected by the preference flags or by explicit user / lead override.
- `parallelMode` is the general orchestrator rule for whether independent helper lanes should be parallelized by judgment at all; external adapter fan-out is one overlay on top of that rule.
- Multiple external adapters may run in parallel when their scopes are independent, `parallelMode` permits ordinary parallel fan-out, and the selected provider runtimes support concurrent non-interactive execution.
- Do not cap that fan-out at one instance per helper or provider: the same external helper and the same resolved provider may be launched multiple times concurrently when each run owns a different admitted artifact or disjoint slice.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not replace the general `parallelMode` rule or forbid brigade-style reuse of the same provider across different independent lanes or slices.
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
| `balanced` | `advisory.repo-understanding` | `claude > codex > claude-secret` |
|  | `advisory.design-adr` | `claude > codex > claude-secret` |
|  | `review.pre-pr` | `claude > codex > claude-secret` |
|  | `review.performance-architecture` | `claude > codex > claude-secret` |
|  | `worker.default-implementation` | `codex > claude` |
|  | `worker.systems-performance-implementation` | `codex > claude` |
|  | `worker.long-autonomous` | `claude > codex` |
|  | `worker.ui-structural-modernization` | `codex > claude` |
|  | `worker.ui-surgical-patch-cleanup` | `codex > claude` |
|  | `worker.visual-icon-decorative` | `codex > claude` |
|  | `review.visual` | `claude > codex > claude-secret` |

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
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing Codex, Claude, Gemini, or Qwen availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution.
- Before honoring `externalClaudeApiMode`, classify the selected lane name. Only `advisory.*` and `review.*` profile lanes may retain `claude-secret`; worker, implementation, repository-hygiene, installer, publication, or other lanes must strip or ignore it.

## Shared lane-priority matrix

| Lane | Priority |
| --- | --- |
| `advisory.repo-understanding` | `claude > codex > claude-secret` |
| `advisory.design-adr` | `claude > codex > claude-secret` |
| `review.pre-pr` | `claude > codex > claude-secret` |
| `review.performance-architecture` | `claude > codex > claude-secret` |
| `worker.default-implementation` | `codex > claude` |
| `worker.systems-performance-implementation` | `codex > claude` |
| `worker.long-autonomous` | `claude > codex` |
| `worker.ui-structural-modernization` | `codex > claude` |
| `worker.ui-surgical-patch-cleanup` | `codex > claude` |
| `worker.visual-icon-decorative` | `codex > claude` |
| `review.visual` | `claude > codex > claude-secret` |

Rules:

- `auto` resolves against this matrix, not against the host-pack name.
- Repo-local heuristics may refine the lane choice, but they must not invent a different provider universe.
- Ordinary `auto` must not resolve to the same provider as the current host line.

## Provenance header

Every external or consultant memo/report should record one explicit execution record with these separate fields:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <eligible internal role label | none>`
- `Requested provider: <internal | codex | claude | gemini | qwen>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | Qwen Code | none>`
- `Requested consultant mode: <external | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | external CLI (Qwen Code) | role disabled>`
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
