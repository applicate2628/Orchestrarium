# Agents-Mode Reference

Canonical value-by-value operator reference for pack-local `agents-mode` files. Keep full `value | meaning` semantics here and let local manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surface in this branch

| Provider | Canonical file | Provider-specific note |
|---|---|---|
| Gemini CLI | `.gemini/.agents-mode` | Shared routing semantics for the Gemini line. Official Gemini runtime config still lives in `.gemini/settings.json`; Orchestrarium install seeds the overlay, while Gemini `/init` still owns `GEMINI.md`. The shared provider universe is `auto | codex | claude | gemini`. `auto` resolves through the active named priority profile, then applies the self-provider filter, so same-provider work requires an explicit override. Gemini remains the preferred target for image, icon, and decorative visual lanes when that routing remains honest. Gemini may store `externalClaudeSecretMode` and `externalClaudeApiMode` because Claude is a valid resolved provider on this line. |

## Canonical maintenance

- Any tool or skill that reads an existing `.gemini/.agents-mode` file to make a routing or operator-mode decision must normalize that file to the current canonical format before trusting the flags.
- Treat comment-free files, partially populated files, older layouts, and stale shipped profile blocks as legacy input that must be rewritten rather than preserved verbatim.
- Read-time normalization preserves the effective values of known keys, preserves unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline allowed-value comments, rewrites the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version, and restores canonical key order.
- This maintenance rewrite happens on read, not only on explicit toggle or init writes. A status-style read is still expected to leave the file in current canonical form after parsing.
- `externalOpinionCounts` is a same-lane distinct-opinion contract, not a generic concurrency cap. The lead may still launch repeated same-provider external helpers in parallel across disjoint slices through the dedicated `external-brigade` surface.

## Init-time presets

Presets are init-time shortcuts only. They expand into canonical `agents-mode` keys. The preset name is NOT persisted in the file — only the resolved key values are written.

| Preset | Role | When to use |
|---|---|---|
| `default` | safe-init only | First-time bootstrap; quiet shared baseline with no standing external preference |
| `absolute-balance` | true everyday center | Daily operation with moderate delegation, internal consultant availability, and external review preference |
| `external-aggressive` | aggressive external use | Maximize external execution on preferred lanes while keeping the stored file canonical |
| `correctness-first` | no-time-limit correctness | Favor deeper validation, forced delegation, forced MCP use, and multi-opinion advisory or review lanes |
| `max-speed` | lowest-friction throughput | Minimize latency and ceremony; prefer project workdirs and no extra opinion overhead |

Routing conventions (not persisted as keys):
- **same-host fast-path**: under `external-aggressive` and `max-speed`, when neutral isolation is not required, allow per-invocation explicit self-provider override.
- **overflow means spill, not serialize**: under `external-aggressive`, internal slot saturation pushes independent eligible lanes into `$external-worker`, `$external-reviewer`, or `$external-brigade` by default.

See `Orchestrarium/docs/agents-mode-reference.md` for the full preset expansion table.

## Shared keys

### `consultantMode`

| Value | Meaning | Ordinary optional consultant use | Mandatory batch-close external consultant-check |
|---|---|---|---|
| `external` | External-only consultant | Use the selected external CLI only. If it is unavailable or fails, return an unavailable advisory memo and keep routing honest. | Do not downgrade to internal fallback. Return an unavailable advisory memo and keep the batch open for escalation. |
| `internal` | Internal-only consultant | Use the internal consultant path for ordinary optional second-opinion work. | Unavailable in this mode because the batch-close check is explicitly external. Keep the batch open for escalation. |
| `disabled` | Consultant disabled | Skip ordinary optional second-opinion use. | Unavailable in this mode. Return an unavailable advisory memo and keep the batch open for escalation. |

Notes:
- No config file behaves like consultant-disabled for ordinary optional consultant use.
- `consultantMode` governs consultant behavior only. It does not replace reviewer, QA, or human publication gates, and `external` never authorizes an internal fallback.

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
| `false` | No default worker preference | Eligible worker-side roles may still route to an external worker path when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external worker adapter | Eligible non-owner, non-review roles should prefer the external worker path as the default routing choice. |

### `preferExternalReviewer`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default reviewer preference | Eligible review or QA roles may still route to an external reviewer path when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external review adapter | Eligible review and QA roles should prefer the external reviewer path as the default routing choice. |

### `externalProvider`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | Use the active named priority profile, then apply the self-provider filter | Resolve the provider by lane type through `externalPriorityProfiles[externalPriorityProfile]`. If the top choice would collapse into the current host line, ordinary `auto` must skip it; same-provider execution requires an explicit override. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. |
| `claude` | Route provider-backed external work to Claude CLI | Valid wherever Claude CLI is installed. When this value is selected, honor `externalClaudeSecretMode` and `externalClaudeApiMode`. |
| `gemini` | Route provider-backed external work to Gemini CLI | Valid wherever Gemini CLI is installed. |

Notes:
- `externalProvider` selects the external CLI for provider-backed consultant, `$external-worker`, and `$external-reviewer` execution.
- The shared provider universe is `auto | codex | claude | gemini`.
- Provider selection is lane-driven, not host-pack-driven.
- If the selected provider is unavailable, the role does not pretend the same provider-backed run succeeded locally; the orchestrator must disclose the failure and reroute explicitly.
- Provider-backed consultant execution in `external` mode and both external adapter roles must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not satisfy that route by spawning an internal agent/helper/subagent host.
- `externalProvider: gemini` is an explicit self-provider override only. Ordinary `auto` must not self-bounce.
- Gemini remains preferred for image, icon, and decorative visual lanes when the active profile keeps that routing honest.

### `externalPriorityProfile`

| Value | Meaning | Expected behavior |
|---|---|---|
| `balanced` | Ordinary baseline profile | Mirrors the current shared lane matrix. This is the default when the key is absent. |
| `gemini-crosscheck` | Gemini-inclusive cross-check profile | Keeps Gemini inside the non-visual advisory and pre-PR review cross-check lanes so a second opinion can include Gemini without changing the visual-first routing story. |

Notes:
- Unknown profile names must fail closed rather than silently falling back to a different profile.
- The active profile is selected by `externalPriorityProfile`; if it is missing, treat it as `balanced`.

### `externalPriorityProfiles`

| Shape | Meaning |
|---|---|
| profile name -> lane -> ordered provider list | Stores the selectable provider order for each lane in each named profile |

Current canonical profiles:

| Profile | Lane | Priority |
|---|---|---|
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

Notes:
- The `balanced` profile is the ordinary shared matrix.
- The `gemini-crosscheck` profile is the explicit cross-check profile for cases where one independent external opinion is not enough and Gemini should be part of the non-visual advisory/review set.
- Use `worker.systems-performance-implementation` for Rust hot paths, systems/perf-sensitive implementation, and media-pipeline work; keep `worker.default-implementation` for ordinary worker-side implementation.
- Use `worker.ui-structural-modernization` for broad UI scaffold, layout rewrite, and modernization work; use `worker.ui-surgical-patch-cleanup` for exact patch, cleanup, and partial-edit correction work.
- Use `review.performance-architecture` for performance/architecture review and hot-path cross-checks instead of overloading `review.pre-pr`.
- Keep the nesting capped at `profile -> lane -> ordered provider list`; do not introduce deeper role-level nesting.

### `externalOpinionCounts`

| Shape | Meaning |
|---|---|
| lane -> integer | Declares how many distinct external opinions to collect for that lane |

Notes:
- Missing lane counts mean `1`.
- Keep the default quiet unless a lane explicitly asks for more than one external opinion.
- When a lane asks for more than one opinion, the lead may invoke multiple eligible external adapters in parallel and aggregate them fail closed.
- When a bounded batch needs multiple parallel external helpers, use `external-brigade` instead of inflating `externalOpinionCounts`.

### `external<Provider>WorkdirMode`

| Value | Meaning | Expected behavior |
|---|---|---|
| `neutral` | Fresh neutral empty working directory | Launch the resolved provider in a fresh empty neutral directory by default and pass project context explicitly through the prompt, admitted artifacts, or attached paths instead of inheriting repo-local instruction surfaces implicitly. |
| `project` | Current project or worktree directory | Launch the resolved provider in the current project or worktree when the external run must directly see repo-local files, tools, or instruction surfaces in place. |

Keys:
- `externalCodexWorkdirMode`
- `externalClaudeWorkdirMode`
- `externalGeminiWorkdirMode`

Notes:
- These keys are provider-specific execution-directory policies, not provider selectors and not transport selectors.
- `neutral` is the first-write default for all three keys.
- The ordinary default should be a neutral empty directory so comparative or external runs do not accidentally inherit repo-local instruction overlays by cwd alone.
- When the resolved provider is `codex`, honor `externalCodexWorkdirMode`; when it is `claude`, honor `externalClaudeWorkdirMode`; when it is `gemini`, honor `externalGeminiWorkdirMode`.

### `externalClaudeSecretMode`

| Value | Meaning | Effective Claude CLI behavior |
|---|---|---|
| `auto` | Limit-triggered SECRET-backed retry | Start with the plain Claude command. If that call fails on quota, limit, or reset errors, rerun the same one-line Claude command once with `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` added to that command environment. |
| `force` | SECRET-backed primary Claude call | Apply the same `ANTHROPIC_*` values from the local Claude `SECRET.md` to the first Claude call immediately. Do not perform a second SECRET-backed retry because the primary call already used that environment override. |

Notes:
- This key is valid on the Gemini line when `externalProvider` resolves to `claude`, including the `auto` default.
- `auto` is the first-write default.
- If the required `ANTHROPIC_*` values cannot be read from the local Claude `SECRET.md`, disclose that explicitly. `force` must not silently fall back to a plain Claude call, and `auto` must not claim that the retry happened when it did not.

### `externalClaudeApiMode`

| Value | Meaning | Effective Claude transport behavior |
|---|---|---|
| `disabled` | No Claude API transport | Use only the allowed Claude CLI path. If that path fails, Claude is unavailable. |
| `auto` | Claude CLI first, then `claude-api` fallback | Run the allowed Claude CLI path first, including any `externalClaudeSecretMode` retry semantics. If Claude still fails because of CLI availability, auth, quota, limit, or reset errors, retry once through the local `claude-api` command when it is installed. |
| `force` | Claude API primary transport | Use `claude-api` as the first Claude transport immediately and do not spend time on a preceding Claude CLI attempt. |

Notes:
- This key is valid on the Gemini line when `externalProvider` resolves to `claude`, including the `auto` default.
- `auto` is the first-write default.
- `claude-api` is the repo-local named secondary transport; it must be available on PATH for `auto` fallback or `force` primary mode to succeed.
- This key selects transport, not provider. It does not authorize switching away from the resolved Claude provider.

## External role eligibility

Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Meaning |
|---|---|---|
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker or review lane. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the slot as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the slot as review or QA work. |
| Owner roles such as `$product-manager` or `$lead` | unsupported | There is no generic external owner adapter. Fail fast before probing provider CLI availability and reroute honestly. |

Notes:
- An explicit user request for `external` does not create a new adapter type. Owner roles stay unsupported unless a repository defines a dedicated external owner adapter explicitly.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` stay eligible for `$external-worker` when routing selects external substitution.
- Independent eligible external lanes may run in parallel when the provider runtimes support it. Native internal slot limits are not a reason to silently serialize or drop ready external work.

## Multi-opinion aggregation

- When `externalOpinionCounts[lane]` is greater than `1`, collect distinct eligible providers in profile order until the count is satisfied or the profile runs out of eligible providers.
- If the requested count cannot be satisfied, fail closed with `BLOCKED` and keep any collected opinions as evidence, but do not advance the gate.
- For advisory and review lanes, any returned `REVISE` or `BLOCKED` verdict blocks gate advancement unless a stricter repo-local rule overrides it explicitly.
- Gemini can participate in non-visual advisory and review lanes when the active profile ranks it inside the requested opinion count; this is a profile choice, not a special-case exception.

## First-write defaults

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalPriorityProfile` | `externalCodexWorkdirMode` | `externalClaudeWorkdirMode` | `externalGeminiWorkdirMode` | `externalClaudeSecretMode` | `externalClaudeApiMode` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gemini CLI | requested value | `manual` | `auto` | `false` | `false` | `auto` | `balanced` | `neutral` | `neutral` | `neutral` | `auto` | `auto` |

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
| External routing order | Check role eligibility first. Only supported external buckets proceed to provider resolution and CLI availability checks. |
| External parallelism | If independent eligible lanes are ready and provider runtimes support it, multiple external adapters may run concurrently. Native internal slot limits are not a reason to drop or silently serialize otherwise-ready external lanes. Same-provider helper fan-out across disjoint slices belongs to `external-brigade`, not to `externalOpinionCounts`. |
| External adapter availability | External worker and reviewer paths do not silently fall back inside the role. If the selected external CLI is unavailable, the orchestrator must disclose the failure and reroute explicitly. |
| Direct external launch | Provider-backed consultant execution in `external` mode and both external adapter roles must launch the selected external transport directly. If the host runtime cannot do that, the route is disabled rather than proxied through an internal helper. |
| Claude SECRET mode | `externalClaudeSecretMode: auto` keeps the limit-triggered retry path, while `force` applies the same `ANTHROPIC_*` environment to the primary Claude call. Both modes stay on the same provider. |
| Claude API mode | `externalClaudeApiMode: auto` keeps Claude CLI first and then tries `claude-api` as the named secondary Claude transport; `force` starts on `claude-api` immediately. |
| External workdir mode | `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each external provider runs in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`. |
| Shared provider universe | `externalProvider: auto` uses the active named priority profile and then applies the self-provider filter. There is no host-line default provider baked into the Gemini pack. That self-provider filter is a repo-local routing rule, not an official provider-wide ban on invoking Gemini from Gemini. |
| Repo-local visual heuristic | Gemini is the top shared-matrix target for image, icon, and decorative visual lanes, but ordinary `auto` still respects the self-provider filter. Same-provider routing requires an explicit override. |
| Unknown keys | Tools that update `.gemini/.agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it to a consultant-only shape. |
