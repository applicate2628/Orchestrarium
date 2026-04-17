# Agents-Mode Reference

Canonical value-by-value operator reference for pack-local `agents-mode` files. Keep full `value | meaning` semantics here and let root manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surfaces

| Provider | Canonical file | Provider-specific note |
|---|---|---|
| Codex | `.agents/.agents-mode.yaml` | Shares the canonical provider universe `auto | codex | claude | gemini`. `auto` resolves by lane type through the active named profile below; explicit `codex` is a self-provider override only, never the ordinary `auto` result. Decision-driving reads resolve Codex overlay state in this order: local `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, global `~/.codex/.agents-mode.yaml`, then global legacy `~/.codex/.agents-mode`; whichever file supplies the effective config must be normalized forward into the canonical `.yaml` path in the same scope. Codex-line config may store the shared `externalModelMode`, `externalGeminiFallbackMode` when Gemini is the resolved provider, `externalClaudeApiMode` when Claude is the resolved provider, and optional `externalClaudeProfile` when Codex dispatches to Claude. |
| Claude Code | `.claude/.agents-mode.yaml` | Shares the canonical provider universe `auto | codex | claude | gemini`. `auto` resolves by lane type through the active named profile below; explicit `claude` is a self-provider override only, never the ordinary `auto` result. Decision-driving reads resolve Claude overlay state in this order: local `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, global `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`; whichever file supplies the effective config must be normalized forward into the canonical `.yaml` path in the same scope. The secret-backed Claude API path remains a Claude wrapper transport, not a separate provider. Claude-line config may store the shared `externalModelMode`, `externalGeminiFallbackMode` when Gemini is the resolved provider, and `externalClaudeApiMode` when Claude is the resolved provider. |
| Gemini CLI | `.gemini/.agents-mode.yaml` | Shares the canonical provider universe `auto | codex | claude | gemini`. `auto` resolves by lane type through the active named profile below; explicit `gemini` is a self-provider override only, never the ordinary `auto` result. Decision-driving reads resolve Gemini overlay state in this order: local `.gemini/.agents-mode.yaml`, local legacy `.gemini/.agents-mode`, global `~/.gemini/.agents-mode.yaml`, then global legacy `~/.gemini/.agents-mode`; whichever file supplies the effective config must be normalized forward into the canonical `.yaml` path in the same scope. Official Gemini runtime config still lives in `.gemini/settings.json`; Orchestrarium install seeds the overlay, and Gemini `/init` still owns `GEMINI.md`. Gemini-line config may store the shared `externalModelMode`, `externalGeminiFallbackMode` when Gemini is the resolved provider, and `externalClaudeApiMode` when Claude is the resolved provider. |

Canonical operator-overlay output is now `.agents-mode.yaml` on all three lines. Legacy extensionless `.agents-mode` files remain compatibility input only and must not be recreated as the preferred output.

The exemplar shared default lives in `shared/agents-mode.defaults.yaml`. In the monorepo, installers seed project-local and global `agents-mode` files directly from that shared exemplar and must normalize existing files on reinstall when schema or shipped defaults drift; any provider-only additions are applied at install time instead of living in separate `src.<provider>/agents-mode.defaults.yaml` files. Standalone pack roots still ship one canonical pack-root seed file so those repositories remain self-contained outside the monorepo.

The shipped shared exemplar is intentionally a quiet baseline for first install:
- consultant disabled by default
- delegation manual by default
- parallel routing by judgment by default
- MCP automatic by default
- no standing preference for external worker or reviewer lanes
- `balanced` as the default named external priority profile
- provider runtime defaults by default, with an opt-in shared `pinned-top-pro` model policy for stronger external runs
- neutral workdirs and automatic Claude secondary-transport behavior by default

## Canonical maintenance

- Any tool or skill that reads an existing `agents-mode` file to make a routing or operator-mode decision must normalize that file to the current canonical format before trusting the flags.
- Read the provider-local `.agents-mode.yaml` first. If it is missing, read the legacy extensionless `.agents-mode` file in the same provider directory as compatibility input only. If both local files are missing, fall back to the matching global provider overlay (`~/.codex/.agents-mode.yaml`, `~/.claude/.agents-mode.yaml`, or `~/.gemini/.agents-mode.yaml`) and then to its legacy extensionless sibling as compatibility input only. Normalize whichever file supplied the effective config forward into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a project-local override on read alone.
- Installers are part of that maintenance contract: if `.agents-mode.yaml` already exists and the canonical schema or shipped defaults have changed, reinstall must rewrite it to the current canonical form instead of preserving stale pack-owned structure verbatim.
- In the monorepo, edit only `shared/agents-mode.defaults.yaml`; do not reintroduce provider-local `src.<provider>/agents-mode.defaults.yaml` duplicates.
- Treat comment-free files, partially populated files, older layouts, and stale shipped profile blocks as legacy input that must be rewritten rather than preserved verbatim.
- Read-time normalization preserves the effective values of known keys, preserves unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments on every canonical scalar key plus every shipped profile/count entry, rewrites the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version, and restores canonical key order.
- This maintenance rewrite happens on read, not only on explicit toggle or init writes. A status-style read is still expected to leave the file in current canonical form after parsing.
- If neither local nor global overlay exists for the active provider line, the effective state is `no file`; skills may then apply their documented no-file semantics or first-write defaults honestly.

## Init-time presets

Presets are init-time shortcuts only. They expand into canonical `agents-mode` keys. The preset name is NOT persisted in the file — only the resolved key values are written.

At init time, the helper may either write the selected preset immediately or enter a manual fine-tune pass. If the user says to use the preset as-is, the helper should skip the key-by-key walkthrough and write the preset-expanded canonical values directly.

### Available presets

| Preset | Role | When to use |
|---|---|---|
| `default` | safe-init only | First-time bootstrap; quiet shared baseline with no standing external preference |
| `absolute-balance` | true everyday center | Daily operation with moderate delegation, internal consultant availability, and external review preference |
| `external-aggressive` | aggressive external use | Maximize external execution on preferred lanes while keeping the stored file canonical |
| `correctness-first` | no-time-limit correctness | Favor deeper validation, forced delegation, forced MCP use, and multi-opinion advisory or review lanes |
| `max-speed` | lowest-friction throughput | Minimize latency and ceremony; prefer project workdirs and no extra opinion overhead |

`absolute-balance` is intentionally named differently from `externalPriorityProfile: balanced` so the init-time preset and the persisted provider-order profile do not get conflated.

### Preset expansion table

| Key | `default` | `absolute-balance` | `external-aggressive` | `correctness-first` | `max-speed` |
|---|---|---|---|---|---|
| `consultantMode` | `disabled` | `internal` | `external` | `external` | `disabled` |
| `externalClaudeApiMode` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `delegationMode` | `manual` | `auto` | `force` | `force` | `auto` |
| `parallelMode` | `auto` | `auto` | `force` | `auto` | `force` |
| `mcpMode` | `auto` | `auto` | `auto` | `force` | `auto` |
| `preferExternalWorker` | `false` | `false` | `true` | `true` | `false` |
| `preferExternalReviewer` | `false` | `true` | `true` | `true` | `false` |
| `externalProvider` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `externalPriorityProfile` | `balanced` | `balanced` | `balanced` | `gemini-crosscheck` | `balanced` |
| `externalOpinionCounts` | all `1` | all `1` | all `1` | advisory+review `2`, others `1` | all `1` |
| workdir modes | all `neutral` | all `neutral` | all `neutral` | all `neutral` | all `project` |
| `externalModelMode` | `runtime-default` | `runtime-default` | `runtime-default` | `pinned-top-pro` | `runtime-default` |
| `externalGeminiFallbackMode` | `auto` | `auto` | `auto` | `auto` | `auto` |
| `externalClaudeProfile` (Codex-line only) | `opus-max` | `sonnet-high` | `sonnet-high` | `opus-max` | `sonnet-high` |

`correctness-first` lane-specific opinion counts:
- `advisory.repo-understanding: 2`
- `advisory.design-adr: 2`
- `review.pre-pr: 2`
- `review.performance-architecture: 2`
- all other lanes: `1`

### Routing conventions (not persisted)

- **same-host fast-path**: under `external-aggressive` and `max-speed`, when neutral isolation is not required, allow per-invocation explicit self-provider override. The stored file stays canonical; this is a routing rule, not a persisted key.
- **overflow means spill, not serialize**: under `external-aggressive`, internal slot saturation pushes independent eligible lanes into `$external-worker`, `$external-reviewer`, or `$external-brigade` by default. Current rules already allow this; the preset makes it the expected interpretation.

## Shared keys

### `consultantMode`

| Value | Meaning | Ordinary optional consultant use | Batch-close consultant behavior |
|---|---|---|---|
| `external` | External-only consultant | Use the selected external CLI only. If it is unavailable or fails, return an unavailable advisory memo and keep routing honest. | If the lead or repo-local lane policy explicitly asks for a closeout consultant sweep, run it externally. Do not downgrade to internal fallback. |
| `internal` | Internal-only consultant | Use the internal consultant path for ordinary optional second-opinion work. | If the lead or repo-local lane policy explicitly asks for a closeout consultant sweep, run it internally. Do not invent an external-only requirement from `consultantMode` itself. |
| `disabled` | Consultant disabled | Skip ordinary optional second-opinion use. | Skip consultant closeout and do not block batch closure on consultant alone. |

Notes:
- No config file behaves like consultant-disabled for ordinary optional consultant use.
- `consultantMode` governs consultant behavior only. It does not replace reviewer, QA, or human publication gates, and `external` never authorizes an internal fallback.
- `consultantMode` governs consultant availability itself. `consultantMode: disabled` disables consultant use entirely, including any default closeout sweep.
- If a repository wants consultant input at closeout, it must request that policy explicitly; do not infer a hidden consultant blocker from the default contract.

### `delegationMode`

| Value | Meaning | Expected behavior |
|---|---|---|
| `manual` | Explicit delegation only | Do not treat ordinary delegation as pre-authorized. Delegate when the user or the governing workflow explicitly requests it. |
| `auto` | Delegation by routing judgment | Treat ordinary delegation as enabled, but still choose locally vs delegated execution based on routing, scope, and specialist fit. |
| `force` | Delegation whenever feasible | Treat delegation as a standing instruction whenever a matching specialist and viable tool path exist. If the tool path is unavailable, say so explicitly instead of pretending the forced delegation happened locally. |

### `parallelMode`

| Value | Meaning | Expected behavior |
|---|---|---|
| `manual` | Explicit parallelism only | Do not treat ordinary parallel fan-out as pre-authorized. Launch helper or subagent lanes in parallel only when the user, the governing workflow, or a repo-local policy explicitly asks for that parallel bundle. |
| `auto` | Parallelism by routing judgment | Treat safe parallelism as available. Launch independent lanes together when dependencies are satisfied, scopes are disjoint, and merge or integration cost is justified. |
| `force` | Parallelize whenever safe | Treat safe parallel launch as a standing instruction across both internal and external lanes. When two or more independent lanes or slices are ready, prefer launching them together instead of serializing, while still respecting dependency order, disjoint ownership, integration, and runtime limits. |

Notes:
- `parallelMode` is the general orchestrator fan-out rule for any helper or subagent lane, not only for external adapters.
- `parallelMode: manual` does not waive an explicit user-requested or repo-policy-required parallel bundle; it only disables ordinary judgment-based parallel fan-out as the default.
- External-specific controls remain overlays on top of `parallelMode`: `externalOpinionCounts` governs same-lane external distinct-opinion requirements, and `external-brigade` governs one bounded parallel external helper set.

### `mcpMode`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | MCP by judgment | Use relevant MCP tools when they are useful, but do not treat MCP usage as mandatory on every step. |
| `force` | MCP whenever relevant | Treat relevant available MCP usage as an explicit standing instruction rather than an optional convenience. If a relevant MCP is unavailable or broken, disclose that constraint explicitly. |

### `preferExternalWorker`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default worker preference | Eligible worker-side roles may still route to `$external-worker` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external worker adapter | Eligible non-owner, non-review roles should prefer `$external-worker` as the default routing choice. |

### `preferExternalReviewer`

| Value | Meaning | Expected routing effect |
|---|---|---|
| `false` | No default reviewer preference | Eligible review or QA roles may still route to `$external-reviewer` when explicitly requested or otherwise justified, but there is no standing preference. |
| `true` | Prefer external review adapter | Eligible review and QA roles should prefer `$external-reviewer` as the default routing choice. |

### `externalProvider`

| Value | Meaning | Expected behavior |
|---|---|---|
| `auto` | Resolve the external provider by lane type through the active named priority profile | `auto` is pack-neutral. It uses the active profile below, explicit user override, and any documented repo-local routing heuristic. Ordinary `auto` must not silently resolve to the same provider as the current host line. |
| `claude` | Route provider-backed external work to Claude CLI | Valid wherever Claude CLI is installed. When this value is selected or `auto` resolves to Claude, honor `externalModelMode` and `externalClaudeApiMode`; Codex may additionally honor `externalClaudeProfile` as a narrower override. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. If selected from the Codex line, treat it as an explicit self-provider override only. |
| `gemini` | Route provider-backed external work to Gemini CLI | Valid wherever Gemini CLI is installed. When this value is selected or `auto` resolves to Gemini, honor `externalModelMode`; if the model policy is pinned, also honor `externalGeminiFallbackMode`. If selected from the Gemini line, treat it as an explicit self-provider override only. |

Notes:
- `externalProvider` selects the external CLI for provider-backed consultant, `$external-worker`, and `$external-reviewer` execution.
- If the selected provider is unavailable, the role does not pretend the same provider-backed run succeeded locally; the orchestrator must disclose the failure and reroute explicitly.
- Provider-backed consultant execution in `external` mode and both external adapter roles must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not satisfy that route by spawning an internal agent/helper/subagent host.
- Any spawned internal subagent, even if prompted to "use Gemini Pro" or another external provider, is still an internal execution path. For `$external-worker` and `$external-reviewer`, `external` means the real provider CLI or approved transport wrapper only.
- `auto` uses the active named provider-order profile and must not silently self-bounce into the same provider line.
- Explicit self-provider selection is allowed only as an override for isolation, profile, transport, or an intentionally independent rerun.
- The secret-backed Claude API path is a secondary Claude transport, not a fourth provider.
- Explicit user override and documented repo-local task-domain heuristics beat the ordinary `auto` meaning.

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

Notes:
- `balanced` is the implicit default profile and should always be available.
- Repo-local heuristics may refine lane classification, but they must not invent a different provider universe.
- Use `worker.systems-performance-implementation` for Rust hot paths, systems/perf-sensitive implementation, and media-pipeline work; keep `worker.default-implementation` for ordinary worker-side implementation.
- Use `worker.ui-structural-modernization` for broad UI scaffold, layout rewrite, and modernization work; use `worker.ui-surgical-patch-cleanup` for exact patch, cleanup, and partial-edit correction work.
- Use `review.performance-architecture` for performance/architecture review and hot-path cross-checks instead of overloading `review.pre-pr`.
- If a repository wants Gemini-first routing for visual lanes, express that through an explicit provider override or a repo-local custom profile rather than assuming the shipped shared profiles already do it.

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
- `externalOpinionCounts` is a same-lane distinct-opinion contract, not a global concurrency cap. It does not prevent the lead from running multiple same-provider helper instances in parallel on different disjoint lanes or slices.
- When a lane asks for `2+` opinions, treat that as a distinct-opinion requirement whenever the provider order and availability make that possible. Reusing one provider repeatedly does not satisfy the opinion count for that same lane unless a repo-local rule says otherwise.
- `parallelMode` is still the general rule for whether helper lanes should be parallelized by judgment at all; `externalOpinionCounts` only changes how many external opinions one lane must collect once that lane is active.
- When bounded parallel same-provider reuse is needed, route that helper set through `/agents-external-brigade` instead of treating opinion counts as a concurrency control.

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

| Value | Meaning | Effective provider behavior |
|---|---|---|
| `runtime-default` | Let the resolved provider choose its default model or profile | Do not inject a stronger pinned model path just because the provider resolved externally. Transport keys still apply, and narrower provider-specific overrides may still win where they exist. |
| `pinned-top-pro` | Use the strongest documented model/profile path for the resolved provider | Start on the strongest documented provider-native model/profile and allow only the bounded same-provider fallback used for usage-limit or quota exhaustion while staying inside the approved version floor and lane policy for that provider. |

Notes:
- This is the shared cross-provider model-selection policy. It applies only after provider resolution.
- `runtime-default` is the first-write default where this key exists.
- `pinned-top-pro` means:
- Codex: `gpt-5.4 --reasoning-effort xhigh`; only `worker.long-autonomous` and similarly fully autonomous low-reasoning worker lanes may retry once on `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path
- Claude: `opus-max`; if the allowed Claude CLI path hits usage-limit or quota exhaustion and `externalClaudeApiMode: auto` permits it, retry once through the installed secret-backed Claude wrapper, or start there immediately when the user explicitly sets `externalClaudeApiMode: force`, while preserving the strongest Claude intent instead of dropping to `sonnet-high`
- Gemini: `gemini-3.1-pro`, then one retry on `gemini-3-flash`
- Provider-specific transport keys still apply after the model/profile path is chosen. For example, Claude still honors `externalClaudeApiMode`.
- Codex-line `externalClaudeProfile`, when explicitly set, remains a narrower override for Claude model/profile selection than the shared `externalModelMode`.
- Do not silently downgrade below `gpt-5.3-codex-spark` on the Codex line or below Gemini 3 on the Gemini line.
- Repo-local policy treats these named fallback paths as alternate limit or budget pools when runtime observation shows that they exhaust independently. They are not quality-equivalent substitutes for the primary path.
- Treat `gpt-5.3-codex-spark` and `gemini-3-flash` as bounded mechanical overflow paths only. Reserve them for strictly scoped, low-reasoning, autonomous work instead of using them as the ordinary cheaper mode for broad reasoning or cleanup.
- Treat the secret-backed Claude wrapper differently: repo-local policy accepts it as the economical near-full-strength Claude transport with slightly weaker settings than the strongest Claude CLI profile, so `externalClaudeApiMode: force` is an explicit budget choice as well as a limit fallback.

## External role eligibility

Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Meaning |
|---|---|---|
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker lane, reviewer, or approver. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the slot as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the slot as review or QA work. |
| Owner roles such as `$product-manager` or `$lead` | unsupported | There is no generic external owner adapter. Fail fast before probing provider CLI availability and reroute honestly. |

Notes:
- An explicit user request for `external` does not create a new adapter type. Owner roles stay unsupported unless a repository defines a dedicated external owner adapter explicitly.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` stay eligible for `$external-worker` when routing selects external substitution.

### `externalGeminiFallbackMode`

| Value | Meaning | Effective Gemini model behavior |
|---|---|---|
| `disabled` | Pro-only Gemini path | Use `gemini-3.1-pro` only. If that Gemini call fails, Gemini is unavailable. |
| `auto` | Gemini 3.1 Pro first, then Gemini 3 Flash fallback | Start with `gemini-3.1-pro`. If that call fails on quota, limit, capacity, `RESOURCE_EXHAUSTED`, or similar retryable provider-capacity errors, rerun the same one-line Gemini command once with `gemini-3-flash`. |
| `force` | Flash-first Gemini path | Use `gemini-3-flash` as the primary Gemini model immediately and do not spend time on a preceding `gemini-3.1-pro` attempt. |

Notes:
- This key matters when the resolved provider is Gemini and the chosen model policy is pinned rather than runtime-default.
- `auto` is the first-write default where this key exists.
- This key changes only the Gemini model path inside the Gemini provider. It does not authorize provider switches or silent reroutes to Claude or Codex.
- Under `externalModelMode: runtime-default`, do not inject an extra explicit Gemini model hop or an extra fallback retry through this key.
- The current shipped Gemini baseline is `gemini-3.1-pro` with `gemini-3-flash` as the named fallback. If Google renames the stable model aliases again, update both names in one canonical change instead of mixing generations.
- `force` is a deliberate budget or alternate-limit path for tightly bounded mechanical work only. Do not default reasoning-heavy, ambiguous, or cleanup-heavy work to Flash just to save tokens.

### `externalClaudeApiMode`

| Value | Meaning | Effective Claude transport behavior |
|---|---|---|
| `disabled` | No secret-backed Claude API transport | Use only the allowed Claude CLI path. If that path fails, Claude is unavailable. |
| `auto` | Claude CLI first, then secret-backed fallback | Run the allowed Claude CLI path first. If Claude still fails because of CLI availability, auth, quota, limit, or reset errors, retry once through the installed Claude wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`. |
| `force` | Secret-backed Claude API primary transport | Use the installed Claude wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` as the primary Claude transport and do not spend time on a preceding Claude CLI attempt. |

Notes:
- This key is relevant whenever the resolved provider is Claude.
- `auto` is the first-write default where this key exists.
- The preferred Claude API transport surface is the installed wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`, which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` values, and then launches plain `claude`.
- If that wrapper surface is unavailable, `auto` fallback or `force` primary mode must fail closed instead of pretending a direct `claude-api` binary exists.
- This key selects transport, not provider. It does not authorize switching away from the resolved Claude provider.
- Repo-local policy allows `externalClaudeApiMode: force` as an explicit economy choice because the secret-backed Claude path remains close enough to full Claude behavior for ordinary admitted lanes, even though its settings are not identical to the strongest plain Claude CLI profile.
- When the plain Claude CLI path and the Claude API transport consume different limits in practice, describe that as observed runtime behavior or repo-local operator policy rather than as an official provider guarantee.

## Practical launch rules

| Situation | Rule |
|---|---|
| `externalModelMode: pinned-top-pro` and Codex is the chosen provider | Try `gpt-5.4 --reasoning-effort xhigh` first. Only on `worker.long-autonomous` or another explicitly fully autonomous low-reasoning worker lane may Codex retry once with `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path. Other lanes must disclose Codex unavailability instead of downgrading. |
| `externalModelMode: pinned-top-pro` and Gemini is the chosen provider | Try `gemini-3.1-pro` first. If Gemini returns quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style errors, retry once with `gemini-3-flash`. |
| `externalModelMode: pinned-top-pro` and Claude is the chosen provider | Try `opus-max` first unless the user explicitly sets `externalClaudeApiMode: force`, in which case start on the secret-backed Claude wrapper immediately. Under `externalClaudeApiMode: auto`, if Claude hits CLI/auth/usage-limit or quota-style failure, keep the strongest Claude model intent and retry once through the allowed secret-backed Claude transport instead of downgrading to `sonnet-high`. |
| Claude CLI is the chosen provider and is already authenticated | Use the plain Claude CLI path first. |
| Claude CLI is not logged in, or auth is intentionally repo-local | Prefer the installed Claude API wrapper allowed by `externalClaudeApiMode` instead of repeatedly probing a plain `claude` command that cannot authenticate. |
| PowerShell Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.ps1`. The wrapper must work on Windows PowerShell 5.1 and PowerShell 7+, it accepts both `-PrintSecretPath` and `--print-secret-path`, and forwarded Claude flags should be passed after `--%`. |
| Bash / Git Bash Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.sh`. The wrapper launches plain `claude`; if the active shell cannot see that binary, set `CLAUDE_BIN` explicitly. |
| Codex commit review | Use `codex review --commit <sha>` without an extra free-form prompt. If custom review instructions are required, prefer a narrower `codex exec` run on the admitted scope instead of mixing text with `review --commit`. |
| Wide release or parity audit | Split by admitted repo, file set, or lane. Do not default to one mega neutral-dir prompt over the whole pack family because Codex and Gemini are more likely to stall on ultra-wide review scopes. |
| Neutral workdir mode | Keep `external<Provider>WorkdirMode: neutral` by default and pass the exact repo, commit, file, or artifact scope explicitly. Switch to `project` only when the external run truly needs in-place filesystem execution or repo-local instruction surfaces. |

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

| Provider | `consultantMode` | `externalClaudeApiMode` | `delegationMode` | `parallelMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalCodexWorkdirMode` | `externalClaudeWorkdirMode` | `externalGeminiWorkdirMode` | `externalModelMode` | `externalGeminiFallbackMode` | `externalClaudeProfile` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Codex | `disabled` | `auto` | `manual` | `auto` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `neutral` | `runtime-default` | `auto` | `opus-max` unless explicitly overridden |
| Claude Code | `disabled` | `auto` | `manual` | `auto` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `neutral` | `runtime-default` | `auto` | not part of canonical Claude-line config |
| Gemini CLI | `disabled` | `auto` | `manual` | `auto` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `neutral` | `runtime-default` | `auto` | not part of canonical Gemini-line config |

Structured defaults written alongside the scalar keys:

| Key | Default |
|---|---|
| `externalPriorityProfile` | `balanced` |
| `externalPriorityProfiles` | ship `balanced` and `gemini-crosscheck` |
| `externalOpinionCounts` | all documented lanes default to `1` unless repo-local policy explicitly raises a lane |

Default-comment guidance:
- In the canonical exemplar, every shipped scalar default should include both the `allowed` set and the explicit `default: ...` value in the inline comment so the first-write value is visible directly in the file.
- `balanced` should stay marked as the default shared routing profile inside the `externalPriorityProfiles` block.

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
| General parallelism mode | `parallelMode` governs whether ordinary helper/subagent fan-out stays explicit-only (`manual`), judgment-based (`auto`), or a standing instruction whenever safe (`force`) across both internal and external lanes. |
| External routing order | Check role eligibility first. Only supported external buckets proceed to provider resolution and CLI availability checks. |
| External parallelism | If `parallelMode` permits it and independent eligible external lanes are ready, multiple external adapters may run concurrently. Internal native slot limits are not a reason to drop or silently serialize otherwise-ready external lanes. |
| Same-provider fan-out | Parallel external work is not capped at one instance per helper or provider. Multiple simultaneous `consultant`, `external-worker`, or `external-reviewer` runs may target the same provider when each run owns a different admitted artifact or disjoint slice. |
| External adapter availability | `$external-worker` and `$external-reviewer` do not silently fall back inside the role. If the external CLI is unavailable, the adapter is disabled and the orchestrator reroutes explicitly. |
| Direct external launch | Provider-backed consultant execution in `external` mode and both external adapter roles must launch the selected external transport directly. If the host runtime cannot do that, the route is disabled rather than proxied through an internal helper. |
| External workdir mode | `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each external provider runs in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`. |
| Shared external model policy | `externalModelMode: runtime-default` keeps provider runtime model selection; `pinned-top-pro` pins the strongest documented model/profile for the resolved provider and allows one named same-provider fallback on retryable provider exhaustion. |
| Gemini fallback mode | `externalGeminiFallbackMode: auto` keeps `gemini-3.1-pro` first and allows one retry on `gemini-3-flash` only for limit, quota, or capacity-style Gemini failures when the model policy is pinned; `force` starts on `gemini-3-flash` immediately. |
| Claude API mode | `externalClaudeApiMode: auto` keeps Claude CLI first and then tries the secret-backed Claude wrapper as the named secondary Claude transport; `force` starts on that wrapper immediately. This is the single Claude wrapper-transport toggle. |
| Active priority profile | `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`. Unknown profile names fail closed. |
| Multi-opinion routing | `externalOpinionCounts` controls how many distinct external opinions a lane must collect under `auto`. Missing counts mean `1`; shortfalls keep the lane `BLOCKED`. It does not replace the general `parallelMode` rule. |
| External brigade | A brigade is a bounded parallel set of external helper runs. It may mix providers or reuse one provider many times, but each brigade item still owns one execution role, one admitted artifact, and one gate, and it remains an external-specific overlay on top of the general `parallelMode` rule. |
| Shared provider universe | All three packs use the same provider universe: `auto | codex | claude | gemini`. |
| Shared lane matrix | `externalProvider: auto` resolves by lane type through the active priority profile instead of by host pack identity. |
| Self-provider rule | Ordinary `auto` must not resolve to the same provider as the host line. Self-provider is explicit-override only. This is a repo-local routing rule, not an official provider-wide ban on invoking the same CLI. |
| Repo-local Gemini cross-check | In this repository, `gemini-crosscheck` is the named profile for bringing Gemini into broader non-visual advisory and review lanes when one independent opinion is not enough. |
| Visual-lane override policy | The shipped shared profiles do not hardwire Gemini-first visual routing. If a repository wants Gemini first for image, icon, or decorative visual lanes, express that through an explicit provider override or a repo-local custom profile. |
| Unknown keys | Tools that update `agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
