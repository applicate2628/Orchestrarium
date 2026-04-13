# Agents-Mode Reference

Canonical value-by-value operator reference for the standalone Codex pack.

## Provider surface in this branch

| Provider | Canonical file | Provider-specific note |
|---|---|---|
| Codex | `.agents/.agents-mode` | `externalProvider: auto` resolves by the shared lane matrix and the active priority profile, not by host pack. Explicit `codex`, `claude`, or `gemini` may be selected when the user or routing asks for them. Provider-specific workdir keys default to `neutral`. The shared `externalModelMode` distinguishes runtime-default provider selection from pinned top-model execution. When Gemini is selected, honor `externalModelMode` first and then `externalGeminiFallbackMode` for pinned Gemini fallback. When Claude is selected, honor `externalModelMode`, `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile`. Installs seed the default file into the active target and preserve existing overlays on reinstall. |

New writes should target `agents-mode`. In the umbrella monorepo workspace, this standalone seed is generated from `Orchestrarium/shared/agents-mode.defaults.yaml`; in this branch, the shipped canonical seed file remains `agents-mode.defaults.yaml`.

## Canonical maintenance

- Any tool or skill that reads an existing `agents-mode` file to make a routing or operator-mode decision must normalize that file to the current canonical format before trusting the flags.
- Treat comment-free files, partially populated files, older layouts, and stale shipped profile blocks as legacy input that must be rewritten rather than preserved verbatim.
- Read-time normalization preserves the effective values of known keys, preserves unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline allowed-value comments, rewrites the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version, and restores canonical key order.
- This maintenance rewrite happens on read, not only on explicit toggle or init writes. A status-style read is still expected to leave the file in current canonical form after parsing.

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
| `false` | No default worker preference | Eligible worker-side roles may still route to `$external-worker` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external worker adapter | Eligible non-owner, non-review roles should prefer `$external-worker` as the default routing choice. Risk-sensitive templates or missing external runtime paths may still require rerouting. |

### `preferExternalReviewer`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default reviewer preference | Eligible review or QA roles may still route to `$external-reviewer` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external review adapter | Eligible review and QA roles should prefer `$external-reviewer` as the default routing choice. |

### `externalProvider`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | Use the shared lane matrix, then apply self-provider exclusion and CLI availability | Resolve by lane type, not by host pack. Ordinary `auto` does not self-bounce. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. Treat this as an explicit self-provider override on the Codex line, not as an ordinary `auto` result. |
| `claude` | Route provider-backed external work to Claude CLI | Valid wherever Claude CLI is installed. Honor `externalModelMode`, `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile`, with `externalClaudeProfile` remaining the narrower Claude override. |
| `gemini` | Route provider-backed external work to Gemini CLI | Valid wherever Gemini CLI is installed. When this value is selected or `auto` resolves to Gemini, honor `externalModelMode`; if the model policy is pinned, also honor `externalGeminiFallbackMode`. |

Notes:
- `externalProvider` selects the external CLI for provider-backed consultant, `$external-worker`, and `$external-reviewer` execution.
- `auto` resolves by lane type through the active named priority profile, then applies the explicit-only self-provider rule and CLI availability.
- Explicit self-provider selection is allowed only when requested directly or when routing needs isolation, transport, or profile differences. Ordinary `auto` must not silently self-bounce.
- If the selected provider is unavailable, the role does not pretend the same provider-backed run succeeded locally; the orchestrator must disclose the failure and reroute explicitly.
- Provider-backed consultant execution in `external` mode and both external adapter roles must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not satisfy that route by spawning an internal agent/helper/subagent host.
- Explicit user override and documented repo-local routing heuristics beat the ordinary meaning of `auto`.

### `externalPriorityProfile`

| Value | Meaning | Expected behavior |
|---|---|---|
| `balanced` | Default shared routing profile | Keeps the quiet shared lane priorities that ship by default. |
| `gemini-crosscheck` | Broader Gemini participation profile | Promotes Gemini into earlier non-visual advisory and review positions so raising opinion counts can bring Gemini in without explicit provider override. |
| `<custom name>` | Repo-local named profile | Must exist under `externalPriorityProfiles`; otherwise fail closed instead of silently falling back to another profile. |

Notes:
- Missing `externalPriorityProfile` means `balanced`.
- `externalPriorityProfile` matters only when `externalProvider: auto`. Explicit scalar provider overrides remain single-provider.

### `externalPriorityProfiles`

Shape:

```yaml
externalPriorityProfiles:
  <profile-name>:
    <lane>: [claude, gemini, codex]
```

Guardrails:
- Keep the nesting capped at `profile -> lane -> ordered provider list`.
- Provider names are limited to `codex | claude | gemini`.
- These structured blocks are the approved multi-line exception to older flat one-key-per-line guidance and should be preserved verbatim by update tools.

Recommended shipped profiles:

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
- `balanced` is the implicit default profile and should always be available.
- Repo-local heuristics may refine lane classification, but they must not invent a different provider universe.
- Use `worker.systems-performance-implementation` for Rust hot paths, systems/perf-sensitive implementation, and media-pipeline work; keep `worker.default-implementation` for ordinary worker-side implementation.
- Use `worker.ui-structural-modernization` for broad UI scaffold, layout rewrite, and modernization work; use `worker.ui-surgical-patch-cleanup` for exact patch, cleanup, and partial-edit correction work.
- Use `review.performance-architecture` for performance/architecture review and hot-path cross-checks instead of overloading `review.pre-pr`.
- Visual and decorative lanes may honestly prefer Gemini first when the task is image, icon, or decorative visual work.

### `externalOpinionCounts`

| Value | Meaning | Expected behavior |
|---|---|---|
| omitted or `1` | Single external opinion | Keep current single-provider behavior after the provider order resolves. |
| `2+` | Multi-opinion fan-out on the lane | Walk the ordered provider list, skip unavailable providers and ordinary self-bounce, and collect distinct eligible external opinions until the requested count is satisfied or fail closed. |

Notes:
- Missing `externalOpinionCounts[lane]` means `1`.
- Multi-opinion fan-out applies only when `externalProvider: auto`.
- If the requested opinion count cannot be satisfied from the resolved provider order, the lane stays `BLOCKED`; partial collection is evidence, not success.
- For multi-opinion advisory or review lanes, any returned `REVISE` or `BLOCKED` verdict blocks gate advancement unless a stricter repo-local rule overrides it explicitly.
- `externalOpinionCounts` is a same-lane distinct-opinion policy, not a concurrency cap. It does not limit how many same-provider external items may run in parallel when the slices are disjoint.
- When a bounded batch of helper items should launch and aggregate together, use the repo-local `external-brigade` utility instead of trying to compress the request into one memo or one helper call.

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

### `externalModelMode`

| Value | Meaning | Effective model behavior |
|---|---|---|
| `runtime-default` | Keep the resolved provider on its runtime default model/profile | Do not inject a stronger pinned model path just because external routing picked that provider. |
| `pinned-top-pro` | Use the strongest documented provider-native model/profile path | Start on the strongest documented provider-native model/profile and allow only the bounded same-provider fallback used for usage-limit or quota exhaustion while staying inside the approved version floor and lane policy for that provider. |

Notes:
- `runtime-default` is the first-write default.
- Under `pinned-top-pro`, Codex uses `gpt-5.4 --reasoning-effort xhigh`; only `worker.long-autonomous` and similarly fully autonomous low-reasoning worker lanes may retry once on `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path.
- Under `pinned-top-pro`, Claude uses `opus-max`; if the allowed Claude CLI path hits usage-limit or quota exhaustion and `externalClaudeApiMode: auto` permits it, retry once through `claude-api`, or start there immediately when the user explicitly sets `externalClaudeApiMode: force`, while preserving the strongest Claude intent instead of dropping to `sonnet-high`.
- Under `pinned-top-pro`, Gemini uses `gemini-3.1-pro` then follows `externalGeminiFallbackMode` for the allowed same-provider retry.
- Do not silently downgrade below `gpt-5.3-codex-spark` on the Codex line or below Gemini 3 on the Gemini line.
- Repo-local policy treats these named fallback paths as alternate limit or budget pools when runtime observation shows that they exhaust independently. They are not quality-equivalent substitutes for the primary path.
- Treat `gpt-5.3-codex-spark` and `gemini-3-flash` as bounded mechanical overflow paths only. Reserve them for strictly scoped, low-reasoning, autonomous work instead of using them as the ordinary cheaper mode for broad reasoning or cleanup.
- Treat `claude-api` differently: repo-local policy accepts it as the economical near-full-strength Claude transport with slightly weaker settings than the strongest Claude CLI profile, so `externalClaudeApiMode: force` is an explicit budget choice as well as a limit fallback.
- On the Codex line, `externalClaudeProfile` remains a narrower Claude override than the shared model policy where that override exists.
- This key does not authorize a provider switch by itself.

### `externalGeminiFallbackMode`

| Value | Meaning | Effective Gemini model behavior |
|---|---|---|
| `disabled` | Pro-only Gemini path | Use `gemini-3.1-pro` only. If that path fails, Gemini is unavailable. |
| `auto` | Gemini 3.1 Pro first, then Gemini 3 Flash fallback | Start with `gemini-3.1-pro`. If Gemini fails on quota, limit, capacity, HTTP `429`, `RESOURCE_EXHAUSTED`, or similar retryable provider-capacity errors, rerun the same Gemini call once with `gemini-3-flash`. |
| `force` | Flash-first Gemini path | Use `gemini-3-flash` as the primary Gemini model immediately and do not spend time on a preceding `gemini-3.1-pro` attempt. |

Notes:
- This key is valid on the Codex line when `externalProvider` resolves to `gemini` and the shared model policy is pinned rather than runtime-default.
- `auto` is the first-write default.
- The accepted Gemini baseline is Gemini 3 only: `gemini-3.1-pro` first, `gemini-3-flash` as the named fallback. Do not silently downgrade below Gemini 3.
- `force` is a deliberate budget or alternate-limit path for tightly bounded mechanical work only. Do not default reasoning-heavy, ambiguous, or cleanup-heavy work to Flash just to save tokens.
- Under `externalModelMode: runtime-default`, do not inject an extra explicit Gemini model hop or fallback retry through this key.
- This key selects Gemini model path only. It does not authorize a provider switch.

## Named priority profiles

| Lane | Priority |
|---|---|
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

### `externalClaudeSecretMode`

| Value | Meaning | Effective Claude CLI behavior |
|---|---|---|
| `auto` | Limit-triggered SECRET-backed retry | Start with the plain Claude command. If that call fails on quota, limit, or reset errors, rerun the same one-line Claude command once with `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` added to that command environment. |
| `force` | SECRET-backed primary Claude call | Apply the same `ANTHROPIC_*` values from the local Claude `SECRET.md` to the first Claude call immediately. Do not perform a second SECRET-backed retry because the primary call already used that environment override. |

Notes:
- `auto` is the first-write default.
- If the required `ANTHROPIC_*` values cannot be read from the local Claude `SECRET.md`, disclose that explicitly. `force` must not silently fall back to a plain Claude call, and `auto` must not claim that the retry happened when it did not.
- This key changes only the Claude command environment. It does not authorize provider switches or profile downgrades.

### `externalClaudeApiMode`

| Value | Meaning | Effective Claude transport behavior |
|---|---|---|
| `disabled` | No Claude API transport | Use only the allowed Claude CLI path. If that path fails, Claude is unavailable. |
| `auto` | Claude CLI first, then `claude-api` fallback | Run the allowed Claude CLI path first, including any `externalClaudeSecretMode` retry semantics. If Claude still fails because of CLI availability, auth, quota, limit, or reset errors, retry once through the local `claude-api` command when it is installed. |
| `force` | Claude API primary transport | Use `claude-api` as the first Claude transport immediately and do not spend time on a preceding Claude CLI attempt. |

Notes:
- Repo-local policy allows `externalClaudeApiMode: force` as an explicit economy choice because `claude-api` remains close enough to full Claude behavior for ordinary admitted lanes, even though its settings are not identical to the strongest plain Claude CLI profile.
- When the plain Claude CLI path and the Claude API transport consume different limits in practice, prefer describing that as observed runtime behavior or repo-local operator policy rather than as an official provider guarantee.
- `auto` is the first-write default.
- `claude-api` is the repo-local named secondary transport; it must be available on PATH for `auto` fallback or `force` primary mode to succeed.
- This key selects transport, not provider. It does not authorize switching away from the resolved Claude provider.

### `externalClaudeProfile`

| Value | Meaning | Effective Claude CLI mapping |
|---|---|---|
| `sonnet-high` | Balanced Codex-to-Claude external profile | `--model sonnet --effort high` |
| `opus-max` | Maximum-depth Codex-to-Claude external profile | `--model opus --effort max` |

## First-write defaults

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalPriorityProfile` | `externalPriorityProfiles` | `externalOpinionCounts` | `externalCodexWorkdirMode` | `externalClaudeWorkdirMode` | `externalGeminiWorkdirMode` | `externalModelMode` | `externalGeminiFallbackMode` | `externalClaudeSecretMode` | `externalClaudeApiMode` | `externalClaudeProfile` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Codex | requested value | `manual` | `auto` | `false` | `false` | `auto` | `balanced` | shipped `balanced` + `gemini-crosscheck` | all documented lanes default to `1` | `neutral` | `neutral` | `neutral` | `runtime-default` | `auto` | `auto` | `auto` | `sonnet-high` unless explicitly overridden |

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
| External parallelism | If independent eligible lanes are ready and provider runtimes support it, multiple external adapters may run concurrently. Internal native slot limits are not a reason to drop or silently serialize otherwise-ready external lanes. |
| External adapter availability | `$external-worker` and `$external-reviewer` do not silently fall back inside the role. If the external CLI is unavailable, the adapter is disabled and the orchestrator reroutes explicitly. |
| Direct external launch | Provider-backed consultant execution in `external` mode and both external adapter roles must launch the selected external transport directly. If the host runtime cannot do that, the route is disabled rather than proxied through an internal helper. |
| External workdir mode | `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each external provider runs in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`. |
| Claude SECRET mode | `externalClaudeSecretMode: auto` keeps the limit-triggered retry path, while `force` applies the same `ANTHROPIC_*` environment to the primary Claude call. Both modes stay on the same provider and profile. |
| Claude API mode | `externalClaudeApiMode: auto` keeps Claude CLI first and then tries `claude-api` as the named secondary Claude transport; `force` starts on `claude-api` immediately. |
| Shared external model policy | `externalModelMode: runtime-default` keeps provider runtime model selection; `pinned-top-pro` pins the strongest documented model/profile for the resolved provider and allows one named same-provider fallback on retryable provider exhaustion. |
| Gemini fallback mode | `externalGeminiFallbackMode: auto` keeps `gemini-3.1-pro` first and allows one retry on `gemini-3-flash` only for limit, quota, or capacity-style Gemini failures when the model policy is pinned; `force` starts on `gemini-3-flash` immediately. |
| Shared lane matrix | `externalProvider: auto` resolves by lane type, not by host pack. For this repository, that usually means Claude for advisory and review lanes, Codex for default implementation, and Gemini for visual lanes, with explicit self-provider overrides only when requested. The no-self-bounce part is a repo-local routing rule, not an official provider-wide ban on invoking the same CLI. |
| Repo-local visual heuristic | In this repository, image generation, icon work, and decorative visual polish prefer Gemini as the external provider when that routing remains honest and Gemini is installed. This preference applies to eligible worker-side lanes and visual review or advisory work. |
| External brigade | A brigade is a bounded parallel set of external helper runs. It may mix providers or reuse one provider many times, but each brigade item still owns one execution role, one admitted artifact, and one gate. |
| Unknown keys | Tools that update `.agents/.agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
