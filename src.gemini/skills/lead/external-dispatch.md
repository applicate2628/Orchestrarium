# Gemini External Dispatch Contract

Shared Gemini-line dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer`.

## Canonical config

- Canonical file: `.gemini/.agents-mode`
- Full operator tables: [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md)

Canonical Gemini-line schema:

```yaml
consultantMode: external  # allowed: external | internal | disabled
delegationMode: manual  # allowed: manual | auto | force
mcpMode: auto  # allowed: auto | force
preferExternalWorker: true  # allowed: false | true
preferExternalReviewer: true  # allowed: false | true
externalProvider: auto  # allowed here: auto | codex | claude | gemini
externalPriorityProfile: balanced  # allowed: balanced | gemini-crosscheck
externalPriorityProfiles: {}  # profile -> lane -> ordered provider list
externalOpinionCounts: {}  # lane -> integer
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalGeminiWorkdirMode: neutral  # allowed: neutral | project
externalClaudeSecretMode: auto  # allowed when Claude is selected: auto | force
externalClaudeApiMode: auto  # allowed when Claude is selected: disabled | auto | force
```

Rules:

- `externalProvider` stays scalar and keeps its current meaning for explicit provider overrides.
- `externalProvider: auto` resolves through the active named priority profile and then applies the self-provider filter.
- `externalPriorityProfile` selects the active profile used for `auto`; missing means `balanced`.
- `externalPriorityProfiles` stores the ordered provider lists per lane for each named profile; missing `balanced` means the current shared matrix.
- `externalOpinionCounts` stores how many distinct external opinions to collect per lane; missing entries mean `1`.
- `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each provider-backed external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalClaudeSecretMode` is valid only when the resolved provider is Claude.
- `externalClaudeApiMode` is valid only when the resolved provider is Claude.
- `claude-api` remains a Claude transport, not a fourth provider.
- `externalClaudeProfile` is not part of canonical Gemini-line config.
- Preserve unknown keys on write.
- Any read of `.gemini/.agents-mode` that influences routing must normalize an existing file to the current canonical format before trusting the flags. Comment-free or older-layout files are valid input, not valid output.
- Keep one key per line with inline allowed-value comments.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.
- Gemini remains the preferred target for image, icon, decorative visual, and other clearly visual worker or review lanes when the active profile or repo-local heuristic ranks it first, but ordinary `auto` still respects the self-provider filter.
- `externalProvider: gemini` is an explicit self-provider override only. Ordinary `auto` must not silently self-bounce.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`; when it is Gemini, honor `externalGeminiWorkdirMode`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.

## Named profiles

### `balanced`

- Default profile name.
- Mirrors the current shared lane matrix.
- Keeps the ordinary first-opinion routing unchanged.
- Uses `externalOpinionCounts: 1` unless a repo-local policy explicitly asks for more.

### `gemini-crosscheck`

- Keeps the same worker defaults as `balanced`.
- Raises Gemini into the non-visual advisory and pre-PR review lanes so a second opinion can include Gemini without changing visual-first behavior.
- Intended for cases where one independent external opinion is not enough and the lane policy wants a Gemini cross-check rather than a Gemini-only shortcut.

| Lane | Priority in `gemini-crosscheck` |
|---|---|
| `advisory.repo-understanding` | `claude > gemini > codex` |
| `advisory.design-adr` | `claude > gemini > codex` |
| `review.pre-pr` | `claude > gemini > codex` |
| `worker.default-implementation` | `codex > claude > gemini` |
| `worker.long-autonomous` | `claude > codex > gemini` |
| `worker.visual-icon-decorative` | `gemini > claude > codex` |
| `review.visual` | `gemini > claude > codex` |

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
- Gemini can participate in non-visual advisory and review lanes when the active profile ranks it inside the requested opinion count; this is a profile choice, not a special-case exception.

## Adapter model

- `$external-worker` covers the full worker-side lane.
- `$external-reviewer` is review and QA-side only.
- `$consultant` stays advisory-only.
- The assigned internal role remains provenance metadata only.
- If the selected external CLI is unavailable, the adapter is disabled and the main session reroutes explicitly.
- External adapters do not silently fall back inside the role.
- Independent external adapters may run in parallel when their scopes are independent, the selected provider runtimes support concurrent non-interactive execution, and the requested opinion counts still need more than one provider.
- Do not cap that fan-out at one instance per helper or provider: the same external helper and the same resolved provider may be launched multiple times concurrently when each run owns a different admitted artifact or disjoint slice.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not forbid brigade-style reuse of the same provider across different independent lanes or slices.
- If native internal slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- When multiple independent external lanes should launch together, prefer the pack-local `external-brigade` surface so the main Gemini session records one bounded brigade plan instead of scattering ad hoc parallel helper launches.
- `externalClaudeApiMode: auto` keeps `claude-api` as the named secondary Claude transport after the allowed Claude CLI path is exhausted. `force` starts on `claude-api` immediately.
- If the plain Claude CLI path is selected but is clearly unauthenticated, prefer the allowed Claude API transport instead of repeatedly retrying a plain `claude` command that cannot log in.
- From PowerShell, prefer `.claude/agents/scripts/invoke-claude-api.ps1` when that wrapper surface exists. From Bash or Git Bash, prefer `.claude/agents/scripts/invoke-claude-api.sh`, and set `CLAUDE_API_BIN` explicitly when the active shell PATH differs from the PowerShell PATH.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.

## Eligibility gate

Resolve external dispatch in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Required result |
| --- | --- | --- |
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker or review lane. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the work as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the work as review or QA. |
| Owner roles such as `$product-manager` or `$lead` | unsupported | Fail fast before provider resolution. There is no generic external owner adapter on the Gemini line. |

Rules:

- An explicit request for `external` does not create a new adapter type.
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing Codex, Claude, or Gemini availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution.

## Provenance header

Every external or consultant artifact should record:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <role | none>`
- `Requested provider: <internal | codex | claude | gemini>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | none>`
- `Requested consultant mode: <external | internal | disabled>` or `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual model/profile | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason]>`
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
