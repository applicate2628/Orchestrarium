# Agents-Mode Reference

Canonical value-by-value operator reference for pack-local `agents-mode` files. Keep full `value | meaning` semantics here and let root manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surfaces

| Provider | Canonical file | Provider-specific note |
|---|---|---|
| Codex | `.agents/.agents-mode.yaml` | Shares the production provider universe `auto | codex | claude`, plus the advisory/review-only supplemental `claude-secret` profile candidate. `auto` resolves by lane type through the active named production profile below; explicit `codex` is a self-provider override only, never the ordinary `auto` result. Decision-driving reads resolve Codex overlay state in this order: local `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, global `~/.codex/.agents-mode.yaml`, then global legacy `~/.codex/.agents-mode`; whichever file supplies the effective config must be normalized forward into the canonical `.yaml` path in the same scope. Codex-line config may store the shared `externalModelMode`, `externalClaudeApiMode` for the supplemental `claude-secret` advisory/review candidate, and optional `externalClaudeProfile` when Codex dispatches to primary Claude. |
| Claude Code | `.claude/.agents-mode.yaml` | Shares the production provider universe `auto | codex | claude`, plus the advisory/review-only supplemental `claude-secret` profile candidate. `auto` resolves by lane type through the active named production profile below; explicit `claude` is a self-provider override only, never the ordinary `auto` result. Decision-driving reads resolve Claude overlay state in this order: local `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, global `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`; whichever file supplies the effective config must be normalized forward into the canonical `.yaml` path in the same scope. The secret-backed Claude API path remains a weaker supplemental advisory/review transport, not a separate scalar provider. Claude-line config may store the shared `externalModelMode` and `externalClaudeApiMode`. |
| Gemini CLI | `.gemini/.agents-mode.yaml` | Example-only integration. Gemini is classified by this repository as `WEAK MODEL / NOT RECOMMENDED` and must not appear in shipped `auto` routing profiles. Explicit `externalProvider: gemini` is a manual demonstration path only, not a production recommendation. Decision-driving reads resolve Gemini overlay state in this order: local `.gemini/.agents-mode.yaml`, local legacy `.gemini/.agents-mode`, global `~/.gemini/.agents-mode.yaml`, then global legacy `~/.gemini/.agents-mode`; whichever file supplies the effective config must be normalized forward into the canonical `.yaml` path in the same scope. Official Gemini runtime config still lives in `.gemini/settings.json`; Orchestrarium install seeds the overlay, and Gemini `/init` still owns `GEMINI.md`. |
| Qwen Code | `.qwen/.agents-mode.yaml` | Example-only integration. Qwen is classified by this repository as `WEAK MODEL / NOT RECOMMENDED`, is maintained only as a native example peer to Gemini, and must not appear in shipped `auto` routing profiles. Explicit `externalProvider: qwen` is a manual demonstration path only, not a production recommendation. Official Qwen runtime config uses Qwen-native surfaces such as `QWEN.md`, `.qwen/settings.json`, `.qwen/skills`, `.qwen/agents`, `.qwen/commands`, and `qwen-extension.json`; Orchestrarium Qwen installation must follow those surfaces rather than copying Gemini-specific mechanics. |

Canonical operator-overlay output is now `.agents-mode.yaml` on every provider line. Legacy extensionless `.agents-mode` files remain compatibility input only and must not be recreated as the preferred output.

The exemplar shared default lives in `shared/agents-mode.defaults.yaml`. In the monorepo, installers seed project-local and global `agents-mode` files directly from that shared exemplar and must normalize existing files on reinstall when schema or shipped defaults drift; any provider-only additions are applied at install time instead of living in separate `src.<provider>/agents-mode.defaults.yaml` files. Standalone pack roots still ship one canonical pack-root seed file so those repositories remain self-contained outside the monorepo.

The shipped shared exemplar is intentionally a quiet baseline for first install:
- consultant disabled by default
- delegation manual by default
- parallel routing by judgment by default
- MCP automatic by default
- no standing preference for external worker or reviewer lanes
- `balanced` as the default named external priority profile
- provider runtime defaults by default, with an opt-in shared `pinned-top-pro` model policy for stronger production-provider runs
- neutral workdirs and an advisory/review-only `claude-secret` supplemental candidate available after primary Claude/Codex

## Canonical maintenance

- Any tool or skill that reads an existing `agents-mode` file to make a routing or operator-mode decision must normalize that file to the current canonical format before trusting the flags.
- Read the provider-local `.agents-mode.yaml` first. If it is missing, read the legacy extensionless `.agents-mode` file in the same provider directory as compatibility input only. If both local files are missing, fall back to the matching global provider overlay (`~/.codex/.agents-mode.yaml`, `~/.claude/.agents-mode.yaml`, or `~/.gemini/.agents-mode.yaml`) and then to its legacy extensionless sibling as compatibility input only. Normalize whichever file supplied the effective config forward into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a project-local override on read alone.
- Installers are part of that maintenance contract: if `.agents-mode.yaml` already exists and the canonical schema or shipped defaults have changed, reinstall must rewrite it to the current canonical form instead of preserving stale pack-owned structure verbatim.
- In the monorepo, edit only `shared/agents-mode.defaults.yaml`; do not reintroduce provider-local `src.<provider>/agents-mode.defaults.yaml` duplicates.
- Treat comment-free files, partially populated files, older layouts, and stale shipped profile blocks as legacy input that must be rewritten rather than preserved verbatim.
- Read-time normalization preserves the effective values of known keys, preserves unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, removes example-only providers from every `externalPriorityProfiles` provider list, strips `claude-secret` from non-advisory/non-review lanes, refreshes inline comments on every canonical scalar key plus every shipped profile/count entry, rewrites the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version, and restores canonical key order.
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
| `externalPriorityProfile` | `balanced` | `balanced` | `balanced` | `balanced` | `balanced` |
| `externalOpinionCounts` | all `1` | all `1` | all `1` | advisory+review `2`, others `1` | all `1` |
| workdir modes | all `neutral` | all `neutral` | all `neutral` | all `neutral` | all `project` |
| `externalModelMode` | `runtime-default` | `runtime-default` | `runtime-default` | `pinned-top-pro` | `runtime-default` |
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
| `auto` | Resolve the external provider by lane type through the active named production priority profile | `auto` is pack-neutral. It uses the active production profile below, explicit user override, and any documented repo-local routing heuristic. Ordinary `auto` must not silently resolve to the same provider as the current host line, and it must not select example-only providers. |
| `claude` | Route provider-backed external work to primary Claude CLI | Valid wherever Claude CLI is installed. When this value is selected or `auto` resolves to Claude, honor `externalModelMode`; Codex may additionally honor `externalClaudeProfile` as a narrower override. `externalClaudeApiMode` does not change this primary provider run. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. If selected from the Codex line, treat it as an explicit self-provider override only. |
| `gemini` | Manual example-only Gemini CLI route | `WEAK MODEL / NOT RECOMMENDED`. Valid only as an explicit demonstration or compatibility path where Gemini CLI is installed. It is not eligible for shipped `auto` routing and must not be presented as a production recommendation. |
| `qwen` | Manual example-only Qwen Code route | `WEAK MODEL / NOT RECOMMENDED`. Valid only as an explicit native Qwen integration demonstration where Qwen Code is installed. It is not eligible for shipped `auto` routing and must not be presented as a production recommendation. |

Notes:
- `externalProvider` selects the external CLI for provider-backed consultant, `$external-worker`, and `$external-reviewer` execution.
- If the selected provider is unavailable, the role does not pretend the same provider-backed run succeeded locally; the orchestrator must disclose the failure and reroute explicitly.
- Provider-backed consultant execution in `external` mode and both external adapter roles must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not satisfy that route by spawning an internal agent/helper/subagent host.
- Any spawned internal subagent, even if prompted to "use Gemini Pro" or another external provider, is still an internal execution path. For `$external-worker` and `$external-reviewer`, `external` means the real provider CLI or approved transport wrapper only.
- `auto` uses the active named production provider-order profile and must not silently self-bounce into the same provider line.
- Example-only providers such as Gemini and Qwen are explicit-only. They must not appear in shipped or repo-local `auto` production profiles.
- Explicit self-provider selection is allowed only as an override for isolation, profile, transport, or an intentionally independent rerun.
- The secret-backed Claude API path is exposed as the supplemental `claude-secret` profile candidate for advisory/review lanes only. It is independent of the primary `claude` candidate, appears after primary Claude/Codex in shipped advisory/review orders, and is not a scalar `externalProvider` value.
- Explicit user override and documented repo-local task-domain heuristics beat the ordinary `auto` meaning.

### `externalPriorityProfile`

| Value | Meaning | Expected behavior |
|---|---|---|
| `balanced` | Default shared routing profile | Keeps the quiet shared lane priorities that ship by default. |
| `<custom name>` | Repo-local named production profile | Must exist under `externalPriorityProfiles`; otherwise fail closed instead of silently falling back to another profile. Custom profiles must keep example-only providers out of `auto`. |

Notes:
- Missing `externalPriorityProfile` means `balanced`.
- `externalPriorityProfile` matters only when `externalProvider: auto`. Explicit scalar provider overrides remain single-provider.

### `externalPriorityProfiles`

Shape:

```yaml
externalPriorityProfiles:
  <profile-name>:
    <lane>: [claude, codex]
```

Guardrails:
- Keep the nesting capped at `profile -> lane -> ordered provider list`.
- Provider names in production worker `auto` profiles are limited to `codex | claude`; advisory and review profiles may additionally include `claude-secret` as the last supplemental candidate.
- Example-only providers such as Gemini and Qwen require an explicit scalar provider override and are not valid profile entries.
- These structured blocks are the approved multi-line exception to older flat one-key-per-line guidance and should be preserved verbatim by update tools.

Recommended shipped profiles:

| Profile | Lane | Priority |
|---|---|---|
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

Notes:
- `balanced` is the implicit default profile and should always be available.
- Repo-local heuristics may refine lane classification, but production `auto` profiles must keep worker lanes to `codex | claude`; advisory/review lanes may use `claude-secret` only as the supplemental last candidate.
- Use `worker.systems-performance-implementation` for Rust hot paths, systems/perf-sensitive implementation, and media-pipeline work; keep `worker.default-implementation` for ordinary worker-side implementation.
- Use `worker.ui-structural-modernization` for broad UI scaffold, layout rewrite, and modernization work; use `worker.ui-surgical-patch-cleanup` for exact patch, cleanup, and partial-edit correction work.
- Use `review.performance-architecture` for performance/architecture review and hot-path cross-checks instead of overloading `review.pre-pr`.
- If a repository wants to demonstrate Gemini on visual lanes, use an explicit provider override and document that it is an example-only, not recommended path.

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

Notes:
- These keys are provider-specific execution-directory policies, not provider selectors and not transport selectors.
- `neutral` is the first-write default for both production-provider keys.
- The ordinary default should be a neutral empty directory so comparative or external runs do not accidentally inherit repo-local instruction overlays by cwd alone.
- When the resolved provider is `codex`, honor `externalCodexWorkdirMode`; when it is `claude`, honor `externalClaudeWorkdirMode`.

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
- Claude: `opus-max` for the primary `claude` candidate. The secret-backed wrapper is not a fallback from that candidate; it is the separate weaker `claude-secret` candidate that advisory/review profile order may reach after primary `claude` and `codex`.
- Supplemental candidate keys apply only where their lane policy allows them. For example, `externalClaudeApiMode` governs `claude-secret` availability on advisory/review lanes, not the primary Claude model/profile path.
- Codex-line `externalClaudeProfile`, when explicitly set, remains a narrower override for Claude model/profile selection than the shared `externalModelMode`.
- Do not silently downgrade below `gpt-5.3-codex-spark` on the Codex line.
- Repo-local policy treats these named fallback paths as alternate limit or budget pools when runtime observation shows that they exhaust independently. They are not quality-equivalent substitutes for the primary path.
- Treat `gpt-5.3-codex-spark` as a bounded mechanical overflow path only. Reserve it for strictly scoped, low-reasoning, autonomous work instead of using it as the ordinary cheaper mode for broad reasoning or cleanup.
- Treat the secret-backed Claude wrapper differently: repo-local policy accepts it only as the weaker `claude-secret` advisory/review candidate. It is not a primary-Claude retry path and not a worker, implementation, editing, or publication path.

## External role eligibility

Resolve external routing in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Meaning |
|---|---|---|
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker lane, reviewer, or approver. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the slot as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. The supplemental `claude-secret` candidate is not available to worker-side lanes. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the slot as review or QA work. |
| Owner roles such as `$product-manager` or `$lead` | unsupported | There is no generic external owner adapter. Fail fast before probing provider CLI availability and reroute honestly. |

Notes:
- An explicit user request for `external` does not create a new adapter type. Owner roles stay unsupported unless a repository defines a dedicated external owner adapter explicitly.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` stay eligible for `$external-worker` when routing selects external substitution.
- `claude-secret` is advisory/review-only. It must not be used for worker-side lanes, even when the worker artifact is read-only.

### `externalClaudeApiMode`

| Value | Meaning | Effective `claude-secret` behavior |
|---|---|---|
| `disabled` | No secret-backed Claude API transport | Use only the allowed Claude CLI path. If that path fails, Claude is unavailable. |
| `auto` | Enable supplemental `claude-secret` advisory/review candidate | Keep primary `claude` independent. When an advisory or review profile order reaches `claude-secret`, launch the installed Claude wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` as an additional weak opinion after earlier profile candidates such as `claude` and `codex`. |
| `force` | Force supplemental `claude-secret` availability for advisory/review | Treat `claude-secret` as available for advisory/review lanes when the profile order reaches it, even if the ordinary plain Claude CLI path is unavailable. It still stays after earlier profile candidates and is not a worker or implementation path. |

Notes:
- This key controls only the supplemental `claude-secret` advisory/review candidate. It does not change the primary `claude` provider.
- `auto` is the first-write default where this key exists.
- The preferred Claude API transport surface is the installed wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`, which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`, exports the declared `ANTHROPIC_*` values, and then launches plain `claude`.
- If that wrapper surface is unavailable, `auto` fallback or `force` primary mode must fail closed instead of pretending a direct `claude-api` binary exists.
- This key selects whether the supplemental `claude-secret` candidate may run, not the primary provider. It does not authorize switching a primary `claude` run to the secret-backed wrapper.
- Repo-local policy allows `externalClaudeApiMode: force` only as an advisory/review economy choice. The secret-backed path is weaker than the strongest plain Claude CLI profile and must not be used for worker, implementation, code generation, file editing, or publication actions.
- When the plain Claude CLI path and the Claude API transport consume different limits in practice, describe that as observed runtime behavior or repo-local operator policy rather than as an official provider guarantee.

## Practical launch rules

| Situation | Rule |
|---|---|
| `externalModelMode: pinned-top-pro` and Codex is the chosen provider | Try `gpt-5.4 --reasoning-effort xhigh` first. Only on `worker.long-autonomous` or another explicitly fully autonomous low-reasoning worker lane may Codex retry once with `gpt-5.3-codex-spark` after usage-limit or quota exhaustion on the primary path. Other lanes must disclose Codex unavailability instead of downgrading. |
| Explicit Gemini example route | Gemini is outside production `auto` routing and is classified as `WEAK MODEL / NOT RECOMMENDED`; any direct Gemini command is a manual example or compatibility run, not a pinned production model policy. |
| `externalModelMode: pinned-top-pro` and Claude is the chosen provider | Try primary `claude` on `opus-max`. Do not retry primary Claude through the secret-backed wrapper. Advisory/review lanes may later collect the separate `claude-secret` candidate if their profile order and opinion count reach it. |
| Claude CLI is the chosen provider and is already authenticated | Use the plain Claude CLI path first. |
| Claude CLI is not logged in, or auth is intentionally repo-local | Do not convert a primary `claude` route into a wrapper-backed run. Advisory/review lanes may still reach `claude-secret` as an independent later candidate when enabled. |
| PowerShell Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.ps1`. The wrapper must work on Windows PowerShell 5.1 and PowerShell 7+, it accepts both `-PrintSecretPath` and `--print-secret-path`, and forwarded Claude flags should be passed after `--%`. |
| Bash / Git Bash Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.sh`. The wrapper launches plain `claude`; if the active shell cannot see that binary, set `CLAUDE_BIN` explicitly. |
| External provider CLI prompt payload | Write the substantive task prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism. Keep argv for launcher flags, model/profile options, and file paths; inline prompt strings are only for tiny smoke checks or a documented provider limitation, and the deviation must be recorded. |
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

| Provider | `consultantMode` | `externalClaudeApiMode` | `delegationMode` | `parallelMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalCodexWorkdirMode` | `externalClaudeWorkdirMode` | `externalModelMode` | `externalClaudeProfile` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Codex | `disabled` | `auto` | `manual` | `auto` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `runtime-default` | `opus-max` unless explicitly overridden |
| Claude Code | `disabled` | `auto` | `manual` | `auto` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `runtime-default` | not part of canonical Claude-line config |
| Gemini CLI | example-only | example-only | example-only | example-only | example-only | example-only | example-only | explicit `gemini` only | example-only | example-only | example-only | not part of canonical Gemini-line config |
| Qwen Code | example-only | example-only | example-only | example-only | example-only | example-only | example-only | explicit `qwen` only | example-only | example-only | example-only | not part of canonical Qwen-line config |

Structured defaults written alongside the scalar keys:

| Key | Default |
|---|---|
| `externalPriorityProfile` | `balanced` |
| `externalPriorityProfiles` | ship `balanced` only |
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
| External CLI prompt delivery | Substantive task prompts are file-based by default: create a temporary prompt file and feed it through stdin or a provider-supported file-input mechanism instead of putting the full prompt in argv. |
| External workdir mode | `externalCodexWorkdirMode` and `externalClaudeWorkdirMode` choose whether each production external provider runs in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`. |
| Shared external model policy | `externalModelMode: runtime-default` keeps provider runtime model selection; `pinned-top-pro` pins the strongest documented model/profile for the resolved provider and allows one named same-provider fallback on retryable provider exhaustion. |
| Gemini example status | Gemini is `WEAK MODEL / NOT RECOMMENDED`; use explicit `externalProvider: gemini` only for manual example or compatibility demonstrations, never for shipped `auto` routing. |
| Qwen example status | Qwen is a native example integration peer classified as `WEAK MODEL / NOT RECOMMENDED`; use explicit `externalProvider: qwen` only for manual example or compatibility demonstrations, never for shipped `auto` routing. |
| Claude API mode | `externalClaudeApiMode: auto` enables `claude-secret` as the advisory/review-only supplemental candidate after primary `claude` and `codex`; `force` makes that supplemental candidate available for advisory/review even when plain Claude is unavailable. It is independent of primary `claude` and must not be used for worker or mutating work. |
| Active priority profile | `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`. Unknown profile names fail closed. |
| Multi-opinion routing | `externalOpinionCounts` controls how many distinct external opinions a lane must collect under `auto`. Missing counts mean `1`; shortfalls keep the lane `BLOCKED`. It does not replace the general `parallelMode` rule. |
| External brigade | A brigade is a bounded parallel set of external helper runs. It may mix providers or reuse one provider many times, but each brigade item still owns one execution role, one admitted artifact, and one gate, and it remains an external-specific overlay on top of the general `parallelMode` rule. |
| Production provider universe | Production `auto` routing uses `codex | claude`; example-only providers are explicit-only and excluded from shipped profiles. |
| Shared lane matrix | `externalProvider: auto` resolves by lane type through the active production priority profile instead of by host pack identity. |
| Self-provider rule | Ordinary `auto` must not resolve to the same provider as the host line. Self-provider is explicit-override only. This is a repo-local routing rule, not an official provider-wide ban on invoking the same CLI. |
| Example-provider policy | Gemini and Qwen may be documented as explicit demonstration paths, but they must not enter production `auto` profile orders. |
| Visual-lane override policy | Visual lanes use the same production profile rules as other lanes. Gemini visual use is explicit example-only and not recommended. |
| Unknown keys | Tools that update `agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
