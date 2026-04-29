# Qwen External Dispatch Contract

Shared Qwen-line dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer`.

## Canonical config

- Canonical file: `.qwen/.agents-mode.yaml`
- Legacy `.qwen/.agents-mode` is compatibility input only. Resolve Qwen overlay state in this order: local `.qwen/.agents-mode.yaml`, local legacy `.qwen/.agents-mode`, global `~/.qwen/.agents-mode.yaml`, then global legacy `~/.qwen/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.
- Full operator tables: [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md)

Canonical Qwen-line schema:

```yaml
consultantMode: external  # allowed: external | internal | disabled; default: disabled
externalClaudeApiMode: auto  # controls advisory/review-only claude-secret candidate: disabled | auto | force; default: auto
delegationMode: manual  # allowed: manual | auto | force; default: manual
parallelMode: auto  # allowed: manual | auto | force; default: auto
mcpMode: auto  # allowed: auto | force; default: auto
preferExternalWorker: true  # allowed: false | true; default: false
preferExternalReviewer: true  # allowed: false | true; default: false
externalProvider: auto  # allowed here: auto | codex | claude | gemini | qwen; default: auto; gemini/qwen are WEAK MODEL / NOT RECOMMENDED example-only routes
externalPriorityProfile: balanced  # allowed: balanced | <repo-local production profile>; default: balanced
externalPriorityProfiles: {}  # profile -> lane -> ordered provider list
externalOpinionCounts: {}  # lane -> integer
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalModelMode: runtime-default  # allowed: runtime-default | pinned-top-pro; default: runtime-default
```

Rules:

- `externalProvider` stays scalar and keeps its meaning for explicit provider overrides.
- `externalProvider: auto` resolves through the active named priority profile and then applies the self-provider filter.
- `externalPriorityProfile` selects the active profile used for `auto`; missing means `balanced`.
- `externalPriorityProfiles` stores ordered provider lists per lane for each named profile; missing `balanced` means the current shared production matrix.
- `externalOpinionCounts` stores how many distinct external opinions to collect per lane; missing entries mean `1`.
- `parallelMode: manual` keeps ordinary parallel fan-out explicit-only, `auto` parallelizes safe independent lanes by routing judgment, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified.
- `externalCodexWorkdirMode` and `externalClaudeWorkdirMode` choose whether those provider-backed external runs start in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalModelMode` is the shared cross-provider model-selection policy. `runtime-default` leaves the resolved provider on its runtime default model/profile. `pinned-top-pro` starts on the strongest documented provider-native production path for the resolved provider.
- `externalClaudeApiMode` controls only the supplemental `claude-secret` candidate in advisory/review profile orders. It is independent of primary `claude` and is not a scalar provider, retry, or transport swap.
- `externalClaudeProfile` is not part of canonical Qwen-line config.
- Preserve unknown keys on write.
- Any read of `.qwen/.agents-mode.yaml` that influences routing must normalize an existing file to the current canonical format before trusting the flags. Comment-free or older-layout files are valid input, not valid output.
- Keep one key per line with inline allowed-value comments.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.
- Shipped production `auto` profiles stay on `codex | claude` only. Qwen and Gemini remain explicit example-only providers classified as `WEAK MODEL / NOT RECOMMENDED` and must not appear in a shipped production `auto` profile.
- `externalProvider: gemini` and `externalProvider: qwen` are explicit example-only overrides. Both are `WEAK MODEL / NOT RECOMMENDED`; ordinary `auto` must not silently self-bounce.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.

## Named profiles

### `balanced`

- Default shipped profile name.
- Mirrors the current shared lane matrix.
- Keeps the ordinary first-opinion routing unchanged.
- Uses `externalOpinionCounts: 1` unless a repo-local policy explicitly asks for more.
- Uses `codex | claude` only:
  - advisory lanes: `claude > codex`
  - ordinary worker lanes: `codex > claude`
  - long-autonomous worker lane: `claude > codex`
  - review lanes: `claude > codex`

Repo-local custom production profiles may exist, but they must be declared locally and kept clearly separate from shipped production defaults. Gemini and Qwen must not be profile entries: if a repo wants to demonstrate either example provider, use a scalar explicit provider override such as `externalProvider: qwen` or `externalProvider: gemini` and label the run `WEAK MODEL / NOT RECOMMENDED`.

## Routing algorithm

1. Classify the request into one of the existing lanes: advisory, worker, review, or owner.
2. Reject owner-role substitution unless the role is explicitly eligible for external routing.
3. Resolve the active provider order from `externalPriorityProfiles[externalPriorityProfile][lane]`.
4. If `externalProvider` is explicit, use that single provider and do not fan out.
5. If `externalProvider: auto`, walk the active ordered list, skip unavailable providers, skip ordinary self-bounce on the host line, and collect distinct eligible providers until `externalOpinionCounts[lane]` is satisfied.
6. If the requested opinion count cannot be satisfied, fail closed with `BLOCKED` and keep any collected opinions as evidence, but do not advance the gate.
7. For multi-opinion advisory or review lanes, any returned `REVISE` or `BLOCKED` verdict blocks gate advancement unless a stricter repo-local rule overrides it explicitly.

## Multi-opinion aggregation

- The lead may request more than one external opinion when the active lane policy says a single memo is not enough.
- Each collected opinion must come from a distinct eligible provider whenever the profile and availability make that possible.
- If the profile asks for two opinions and only one eligible provider is available, the route is incomplete and must stop as `BLOCKED`.
- The aggregation rule is fail-closed: for advisory and review lanes, any `REVISE` or `BLOCKED` from the collected opinions blocks advancement unless a stricter repo-local rule says otherwise.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not forbid brigade-style reuse of the same provider across different independent lanes or slices.

## Adapter model

- `$external-worker` covers the full worker-side lane.
- `$external-reviewer` is review and QA-side only.
- `$consultant` stays advisory-only.
- The assigned internal role remains provenance metadata only.
- If the selected external CLI is unavailable, the adapter is disabled and the main session reroutes explicitly.
- External adapters do not silently fall back inside the role.
- `parallelMode` is the general orchestrator rule for whether independent helper lanes should be parallelized by judgment at all; external adapter fan-out is one overlay on top of that rule.
- Independent external adapters may run in parallel when their scopes are independent, `parallelMode` permits ordinary parallel fan-out, the selected provider runtimes support concurrent non-interactive execution, and the requested opinion counts or admitted scopes still justify more than one helper lane.
- Do not cap that fan-out at one instance per helper or provider: the same external helper and the same resolved provider may be launched multiple times concurrently when each run owns a different admitted artifact or disjoint slice.
- If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- When multiple independent external lanes should launch together, prefer the pack-local `external-brigade` surface so the main Qwen session records one bounded brigade plan instead of scattering ad hoc parallel helper launches.
- `externalClaudeApiMode: auto` allows `claude-secret` only when an advisory or review profile order reaches it after primary `claude`/`codex`. `externalClaudeApiMode: force` keeps `claude-secret` available for advisory/review lanes, but it still does not skip earlier primary profile candidates.
- If the plain Claude CLI path is selected and fails, do not silently convert that same primary `claude` run to the wrapper. Advisory/review lanes may later collect `claude-secret` as a separate profile candidate when enabled; worker or mutating routes must report Claude unavailable or reroute honestly.
- From PowerShell, use `.claude/agents/scripts/invoke-claude-api.ps1` only for a resolved `claude-secret` advisory/review candidate and pass forwarded Claude flags after `--%`. From Bash or Git Bash, use `.claude/agents/scripts/invoke-claude-api.sh`, and set `CLAUDE_BIN` explicitly when the active shell PATH differs from the PowerShell PATH.
- On Windows, keep the ordinary external launch path unchanged and try the native Windows shell first. If that native shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- External CLI launches that carry a substantive task prompt must use file-based prompt delivery: write the prompt to a temporary prompt file and feed it through the provider's stdin or supported file-input mechanism. Keep command-line arguments limited to launcher flags, model/profile options, and file paths; inline prompt argv is allowed only for tiny smoke checks or a documented provider limitation, and record that deviation in the execution artifact.

## Eligibility gate

Resolve external dispatch in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Required result |
| --- | --- | --- |
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker or review lane. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the work as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the work as review or QA. |
| Owner roles such as `$product-manager` or `$lead` | unsupported | Fail fast before provider resolution. There is no generic external owner adapter on the Qwen line. |

Rules:

- An explicit request for `external` does not create a new adapter type.
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing Codex, Claude, Gemini, or Qwen availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution.

## Provenance header

Every external or consultant artifact should record:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <role | none>`
- `Requested provider: <internal | codex | claude | gemini | qwen>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | Qwen Code | none>`
- `Requested consultant mode: <external | internal | disabled>` or `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | external CLI (Qwen Code) | role disabled>`
- `Model / profile used: <actual model/profile | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason]>`
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
