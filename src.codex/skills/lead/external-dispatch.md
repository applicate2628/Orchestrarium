# External Dispatch Contract

Shared dispatch contract for `$consultant`, `$external-worker`, and `$external-reviewer` in the Codex pack.

## Canonical config

The project-local config file is:

- `.agents/.agents-mode.yaml`
- Legacy `.agents/.agents-mode` is compatibility input only. Resolve Codex overlay state in this read order (highest to lowest precedence, per-key resolution): local `.agents/.agents-mode.yaml`, local legacy `.agents/.agents-mode`, pack-local global `~/.codex/.agents-mode.yaml`, pack-local global legacy `~/.codex/.agents-mode`, shared cross-pack global `~/.agents-mode.yaml` (alongside `~/.claude.json`), then built-in defaults. Each key resolves to the highest layer that defines it; layers compose, they do not replace each other wholesale. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.

Full value-by-value operator semantics live in `docs/agents-mode-reference.md` in the source repository (maintainer reference; not installed at runtime).

Canonical schema:

```yaml
consultantMode: external  # allowed: external | internal | disabled; default: disabled
delegationMode: auto  # allowed: manual | auto | force; default: auto
parallelMode: auto  # allowed: manual | auto | force; default: auto
mcpMode: auto  # allowed: auto | force; default: auto
preferExternalWorker: true  # allowed: false | true; default: false
preferExternalReviewer: true  # allowed: false | true; default: false
externalProvider: auto  # allowed here: auto | codex | claude | gemini | qwen; default: auto; gemini/qwen are explicit example-only and not recommended for shipped auto
externalPriorityProfile: balanced  # allowed: balanced | quality-first | <repo-local production profile>; default: balanced
reserveResolver: claude-sonnet  # allowed: disabled | claude-sonnet | claude-wrapper | wrapper:<command>; default: claude-sonnet
externalPriorityProfiles: {}  # allowed: structured profile map
externalOpinionCounts: {}  # allowed: structured lane-count map
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalModelMode: runtime-default  # allowed: runtime-default | pinned-top-pro; default: runtime-default
externalCodexProfile: gpt-5.6-sol-xhigh  # allowed: default | gpt-5.6-sol-xhigh | gpt-5.6-sol-max | gpt-5.6-terra; default: gpt-5.6-sol-xhigh
externalClaudeProfile: opus-xhigh  # allowed: sonnet-high | opus-xhigh | opus-max | fable-xhigh; default: opus-xhigh
```

- `consultantMode` controls `$consultant` behavior.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `parallelMode: manual` keeps ordinary parallel fan-out explicit-only, `auto` parallelizes safe independent lanes by routing judgment, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` routes eligible worker-side roles through `$external-worker` by default.
- `preferExternalReviewer` routes eligible reviewer/QA roles through `$external-reviewer` by default.
- `externalProvider` uses the shared provider universe `auto | codex | claude | gemini | qwen`.
- `externalProvider: auto` resolves by lane type through the active production priority profile and opinion-count policy below instead of by host-pack identity. Ordinary `auto` must not silently self-bounce into the current host line's own provider and must not select example-only providers.
- `externalPriorityProfile` chooses which named production routing profile to apply when `externalProvider: auto` is in effect. `balanced` is the quiet default, and `quality-first` is the shipped alternate for maximum result quality. Repo-local custom profiles must keep example-only providers out of production `auto`.
- `reserveResolver` binds the symbolic `reserve` candidate to one concrete read-only resolver: `disabled`, `claude-sonnet`, `claude-wrapper`, or `wrapper:<command>`. `wrapper:<command>` is a PATH-resolved command or repo-relative wrapper path, not an argv prompt channel.
- **Layer-provenance trust gate for executable-bearing values (binding).** `wrapper:<command>` names an arbitrary executable, and the highest-precedence project-local `.agents/.agents-mode.yaml` can arrive inside a cloned repository — an untrusted source that must never silently select code the agent then executes. An executable-bearing value is honored without further confirmation only when a user-global layer (`~/.codex/.agents-mode.yaml`, legacy `~/.codex/.agents-mode`, or `~/.agents-mode.yaml`) defines it or defines the identical value. A project-local `wrapper:<command>` absent from every user-global layer resolves as `reserveResolverTrust: project-UNCONFIRMED` (the machine-readable flag emitted by `scripts/resolve-agents-mode.py`, the executable reference in the source repository) and MUST NOT be launched until the user explicitly confirms it on first use. Record the approval durably by writing the approved value into a user-global layer — that write is what flips subsequent resolutions to `reserveResolverTrust: user-global`. "Approved" wrapper anywhere in this pack's guidance means exactly this mechanism: defined or confirmed at a user-global layer, never a repo-supplied value alone.
- `externalPriorityProfiles` stores the ordered provider lists for each named profile. The shipped profiles live in the structured block below.
- `externalOpinionCounts` stores how many distinct external opinions each lane should collect. Missing lane entries default to `1`.
- `externalCodexWorkdirMode` and `externalClaudeWorkdirMode` choose whether each production-provider external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalModelMode` is the shared cross-provider model-selection policy. `runtime-default` must be resolved to the installed runtime's observed supported model/effort and passed as explicit launch flags before launch — it does NOT leave the provider on an ambient config default. `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows only the bounded same-provider fallback used for usage-limit or quota exhaustion while staying inside that provider's approved version floor and lane policy.
- `externalCodexProfile` is the Codex-specific external profile override after provider resolution. `default` inherits `externalModelMode`, including when `externalProvider: auto` resolves to Codex. `gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes (NOT `gpt-5.6-sol-ultra`, which spawns subagents and must never be shipped on a subagent lane). `gpt-5.6-terra` selects the balanced Codex model (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade) — it must still be verified against the installed runtime before it is reported as used. `gpt-5.6-sol-xhigh` (shipped as the default; symmetric to `externalClaudeProfile: opus-xhigh`) explicitly requests model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`. The advisory/consultant lane runs at HIGH effort by default — Codex `gpt-5.6-sol` + `model_reasoning_effort=xhigh`, Claude `--model opus --effort xhigh` — overriding the operator-set effort knob. `xhigh` is the default for both providers; for especially heavy / complex tasks that genuinely need more depth, the orchestrator may escalate the consultant to the provider's deepest tier (Claude `--effort max`). Never downshift a consultant lane below `xhigh`.
- `reserve` is a symbolic supplemental read-only candidate that may appear only in advisory and review profile orders after primary `claude`/`codex`. It is independent of the primary `claude` candidate, not a scalar provider key, not a primary-provider retry, and not an implementation or editing fallback. The concrete resolver comes from `reserveResolver` and must be recorded in the execution artifact.
- Treat named fallback paths as alternate limit or budget pools only when runtime observation shows they exhaust independently. That is repo-local operator policy, not an official provider guarantee.
- Every provider-backed run MUST carry the resolved model/profile and effort as explicit launch flags in that invocation, even when they equal configured defaults; never rely on provider config defaults. Resolve `runtime-default` to the installed runtime's observed supported model/effort before launch, or report the route unavailable if it cannot be made explicit. Record the exact flags in the execution artifact.
- `externalClaudeProfile` is Codex-line only and selects or overrides the Claude CLI execution profile when `externalProvider` resolves to Claude. Supported values: `sonnet-high` (`--model sonnet --effort high`), `opus-xhigh` (`--model opus --effort xhigh`, the shipped default), `opus-max` (`--model opus --effort max`, max-depth escalation at caller discretion for especially hard tasks), and `fable-xhigh` (`--model fable --effort xhigh`, the current Claude flagship-family best-effort tier — the `fable` flagship alias as of 2026-07, recorded from the installed model list, not a verified capability ranking).
- The preference flags are independent.
- Any write to this file must preserve unknown keys and the other known keys.
- Any read of this file for routing must normalize the effective Codex overlay file to the current canonical format before trusting its flags. Comment-free or older-layout files are valid input, not valid output.
- If local `.agents/.agents-mode.yaml` is missing, read local legacy `.agents/.agents-mode` as compatibility input only; if both local files are missing, fall back through pack-local global `~/.codex/.agents-mode.yaml`, pack-local global legacy `~/.codex/.agents-mode`, then the shared cross-pack global `~/.agents-mode.yaml`, before applying built-in defaults. Normalize whichever file supplied the effective config in place before trusting the flags.
- When writing `.agents/.agents-mode.yaml`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- Writes go to `.agents/.agents-mode.yaml`; preserve unknown keys and the other known keys when updating.
- If the file is created from scratch, write the full default shape: the requested `consultantMode`, `delegationMode: auto`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, `reserveResolver: claude-sonnet`, `externalPriorityProfiles` with the shipped `balanced` and `quality-first` blocks, `externalOpinionCounts` with documented lanes defaulting to `1`, `externalCodexWorkdirMode: neutral`, `externalClaudeWorkdirMode: neutral`, `externalModelMode: runtime-default`, `externalCodexProfile: default`, and `externalClaudeProfile: opus-xhigh` unless the user explicitly requested a different Claude profile.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.

## Routing model

- `$external-worker` and `$external-reviewer` are bidirectional external adapters, not new narrow professions.
- `externalProvider: auto` resolves by lane type through the active production profile and opinion-count policy below instead of by host-pack identity.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`.
- Explicit user override or documented repo-local heuristics may still choose an explicit example-only provider route such as Qwen, or the weaker/not-recommended Gemini path, for demonstration or compatibility work. Shipped production `auto` does not do that.
- Explicit `externalProvider: codex` is a self-provider override only. Ordinary `auto` must not silently self-bounce into the current host line's own provider (the host-line-relative self-bounce rule).
- `externalCodexProfile: default` means Codex inherits `externalModelMode`. `externalCodexProfile: gpt-5.6-sol-max` requests model `gpt-5.6-sol` with `model_reasoning_effort = "max"` for higher-complexity/hard lanes. `externalCodexProfile: gpt-5.6-terra` selects the balanced Codex model tier (a distinct model, `model_reasoning_effort = "high"`, not an effort downgrade) and must record unavailable or deviated if that model cannot be verified against the installed runtime. `externalCodexProfile: gpt-5.6-sol-xhigh` (shipped as default) requests model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` regardless of `externalModelMode`; this is the best-effort sibling of Claude's `opus-xhigh` and is what consultant lane invocations always use.
- `externalModelMode: pinned-top-pro` maps the strongest documented production-provider path as follows when `externalCodexProfile` stays `default`: Codex uses model `gpt-5.6-sol` with `model_reasoning_effort = "xhigh"` through a supported Codex config/profile path; only an explicitly configured repo-local fully autonomous low-reasoning worker lane may retry once on `gpt-5.6-terra` after usage-limit or quota exhaustion on the primary path; Claude uses `opus-max` on the primary `claude` candidate instead of downgrading to `sonnet-high`. `reserve` is a separate symbolic advisory/review candidate after primary `claude`/`codex`, never a retry or transport swap for the primary `claude` candidate. Example-only Gemini and Qwen routes stay explicit/manual and do not add separate production fallback keys to this schema.
- Do not silently downgrade below `gpt-5.6-terra` on the Codex line.
- Use `gpt-5.6-terra` as the balanced cheaper-than-flagship Codex reasoning lane when full `gpt-5.6-sol` depth is not required. It is a genuine reasoning model, review-gated like any external lane.
- Treat `reserve` differently from primary production providers: it is a supplemental advisory/review candidate only. It never grants permission to run implementation, worker-side execution, or editing work through the resolved transport.
- `reserve` is considered only when an advisory or review profile order reaches it after primary `claude`/`codex`; it does not skip earlier primary profile candidates.
- When an advisory or review route resolves to `reserve`, bind it through `reserveResolver`. `claude-sonnet` means the approved Sonnet-style read-only reserve path; `claude-wrapper` means the installed wrapper under `.claude/agents/scripts/invoke-claude-api.ps1` or `.sh`; `wrapper:<command>` means a PATH-resolved command or repo-relative wrapper path such as `tools/reserve-review.ps1`, subject to the layer-provenance trust gate above (a `project-UNCONFIRMED` value must not be launched before first-use user confirmation); `disabled` strips or ignores `reserve`. If the chosen resolver is unavailable, disclose that as a dependency/config failure.
- If the plain Claude CLI path is selected and fails, do not silently convert that same primary `claude` run to the wrapper. Advisory/review lanes may later collect `reserve` as a separate profile candidate when enabled; worker or mutating routes must report Claude unavailable or reroute honestly.
- From PowerShell, use `.claude/agents/scripts/invoke-claude-api.ps1` only when it is the approved resolver for a resolved `reserve` advisory/review candidate and pass forwarded Claude flags after `--%`. From Bash or Git Bash, use `.claude/agents/scripts/invoke-claude-api.sh`, and set `CLAUDE_BIN` explicitly when the active shell PATH differs from the PowerShell PATH.
- On Windows, keep the ordinary external launch path unchanged and try the native Windows shell first. If that native shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- External CLI launches that carry a substantive task prompt must use file-based prompt delivery: write the prompt to a temporary prompt file and feed it through the provider's stdin or supported file-input mechanism. Keep command-line arguments limited to launcher flags, model/profile options, and file paths; inline prompt argv is allowed only for tiny smoke checks or a documented provider limitation, and record that deviation in the execution artifact.
- The Codex pack ships no primary-run prompt wrappers; use a transport-neutral chain that persists the prompt, records an availability probe and explicit launch flags, and captures sibling `.out` / `.err` artifacts. Shipping mirror wrappers is a separate decision, not an inline substitute here.
- After the interactive Trust action, prove host-runnable hook trust with the installed helper: `python ~/.codex/skills/lead/scripts/check-hook-health.py --target ~/.codex/hooks.json --platform codex --codex-trust-mode require`. It reconciles each current owned registration one-to-one with Codex `hooks/list`; `untrusted`, `modified`, missing, duplicate, malformed, or unavailable host state fails. The production installer uses `report` only for identities created or replaced by that same transaction and prints `PENDING_MANUAL_TRUST` until the interactive action is complete.
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

## Prompt-content contract

The prompt file is the only governance an external Command-Line Interface (CLI) inherits. Before launch it must:

- Include the complete handoff template verbatim from the owning `subagent-contracts.md`, including its mandatory pre-dispatch fill rule and defect-class completeness trigger; this contract cites that owner and does not reproduce its field list.
- State the assigned role's gate vocabulary and one-artifact requirement.
- Include a provenance-header echo instruction using this contract's header fields.
- Include the evidence-citation discipline verbatim from the owning `Evidence discipline:` handoff field; this contract does not create a second copy.
- For an adversarial review strategy, use an artifact-only prompt: include the artifact and review scope, but exclude builder claims and self-review.

## Run-completion oracle

- A provider run is complete only when its exit code is recorded, its `.out` artifact exists and is non-empty with the requested artifact shape (provenance header plus gate line), and its `.err` artifact is free of authentication, quota, usage-limit, and mid-stream-truncation markers.
- A failed oracle check makes the run `UNVERIFIED`: re-dispatch it or return `BLOCKED:dependency`. Never summarize a truncated or partial `.out` into an artifact or render it as `PASS`.
- A completion notification — a harness background-task signal, a wrapper exit message, a task callback — or its absence, is never this oracle. Verify the `.out` artifact shape and `.err` cleanliness directly before counting a run done, regardless of any notification.

## Stall and timeout policy

| Effort tier and lane | Earliest valid stall window |
| --- | --- |
| Ordinary advisory | 5-15 minutes |
| `xhigh` / `max` worker or review | 45-60 minutes |

- Actively poll the `.out` / `.err` artifacts and process status. A stall declaration before the applicable window without process evidence violates this contract.
- **Do not wait for a completion notification — the transport-neutral chain provides none.** The Codex pack ships no primary-run prompt wrappers and launches through a transport-neutral chain with no harness re-invoke on the provider's exit, so no completion notification arrives to signal a launched run is done. Active polling of `.out` / `.err` / process status (above) is the only completion signal; a turn that ends "waiting to be notified" strands the run. (A dispatched subagent additionally receives no background-child notification at all — see the no-spawn-and-wait rule in `subagent-contracts.md`.)
- If the shell times out, do not relaunch: identify the running process first and stop it only if it is orphaned or no longer needed.
- A run declared stalled is `UNVERIFIED`; any re-dispatch cites the failed attempt and never duplicates a still-running process.

## Write capability by lane type

- Review, Quality Assurance (QA), and advisory lanes launch with the provider's read-only or sandboxed mode wherever the resolved CLI supports one, and record those permission flags in `Launch flags`.
- A worker lane producing edits from a neutral workdir returns a reviewable edit payload as either a unified diff or a full-file set with repo-relative target paths; the worker artifact names which payload format it used.
- In-place worker editing requires project workdir mode plus the marker-declared isolation worktree defined by decision `2026-07-10-worktree-isolation-canonical-path`; never grant a worker write access to the user's dirty primary tree.
- User override is available in both directions regardless of toggle state.
- Any eligible internal implementer role may be replaced by the best-fit external worker adapter.
- Any eligible reviewer or QA role may be replaced by the best-fit external reviewer adapter.
- `Assigned role` is provenance and routing metadata for the internal role being replaced. It does not narrow the universality of the external adapter.
- QA belongs on the reviewer side.

### `externalPriorityProfiles`

| Profile | Lane | Priority |
| --- | --- | --- |
| `balanced` | `advisory.repo-understanding` | `claude > codex > reserve` |
|  | `advisory.design-adr` | `claude > codex > reserve` |
|  | `design.ui-ux-structure` | `codex > claude` |
|  | `worker.reasoning-constraints` | `claude > codex` |
|  | `worker.default-implementation` | `codex > claude` |
|  | `worker.systems-performance-implementation` | `claude > codex` |
|  | `worker.ui-implementation` | `claude > codex` |
|  | `worker.visual-graphics-visualization` | `claude > codex` |
|  | `review.pre-pr` | `claude > codex > reserve` |
|  | `review.security` | `claude > codex > reserve` |
|  | `review.performance-architecture` | `codex > claude > reserve` |
|  | `review.ui-visual-correctness` | `codex > claude > reserve` |
| `quality-first` | `advisory.repo-understanding` | `codex > claude > reserve` |
|  | `advisory.design-adr` | `codex > claude > reserve` |
|  | `design.ui-ux-structure` | `codex > claude` |
|  | `worker.reasoning-constraints` | `claude > codex` |
|  | `worker.default-implementation` | `codex > claude` |
|  | `worker.systems-performance-implementation` | `codex > claude` |
|  | `worker.ui-implementation` | `claude > codex` |
|  | `worker.visual-graphics-visualization` | `claude > codex` |
|  | `review.pre-pr` | `codex > claude > reserve` |
|  | `review.security` | `codex > claude > reserve` |
|  | `review.performance-architecture` | `codex > claude > reserve` |
|  | `review.ui-visual-correctness` | `codex > claude > reserve` |

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
- Before honoring `reserve`, classify the selected lane name. Only `advisory.*` and `review.*` profile lanes may retain `reserve`; worker, implementation, repository-hygiene, installer, publication, or other lanes must strip or ignore it.

## Shared lane-priority matrix

| Lane | Priority |
| --- | --- |
| `advisory.repo-understanding` | `claude > codex > reserve` |
| `advisory.design-adr` | `claude > codex > reserve` |
| `design.ui-ux-structure` | `codex > claude` |
| `worker.reasoning-constraints` | `claude > codex` |
| `worker.default-implementation` | `codex > claude` |
| `worker.systems-performance-implementation` | `claude > codex` |
| `worker.ui-implementation` | `claude > codex` |
| `worker.visual-graphics-visualization` | `claude > codex` |
| `review.pre-pr` | `claude > codex > reserve` |
| `review.security` | `claude > codex > reserve` |
| `review.performance-architecture` | `codex > claude > reserve` |
| `review.ui-visual-correctness` | `codex > claude > reserve` |

Rules:

- `auto` resolves against this matrix, not against the host-pack name.
- This matrix follows the `full-v2-hard-r2` release-backed `12 + 1` routing read. The `L00 owner/control` line is not encoded here because owner roles have no generic external adapter. Currency: `ASSUMPTION (UNVERIFIED — lane priorities carried over from the gpt-5.5/opus-4.7 release, pending re-benchmark)`; the benchmarked models are retired and the lane orders have not been re-validated on the current families.
- Model-family migration invalidates routing evidence (standing rule): whenever a migration of `externalCodexProfile` or `externalClaudeProfile` retires, renames, or replaces the model family behind any routed lane, the routing-evidence `PASS` is invalidated in the same change — the shipped lane priorities become `ASSUMPTION (UNVERIFIED)`, carried over from the last benchmarked release, until the routing evidence is re-benchmarked or explicitly re-affirmed on the current model families. This is the routing-evidence form of the material-upstream-revision rule: a materially revised accepted upstream artifact marks its dependent downstream artifacts for re-review.
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
- `Launch flags: <exact argv model / effort / sandbox flags>`
- `Run record: <started and finished timestamps or duration; prompt / .out / .err paths>`
- `Deviation reason: <none | external unavailable: [reason] | explicit override>`

Rules:

- Before declaring a route unavailable, run `command -v` or `Get-Command` for the resolved CLI in the current session and record the availability-probe output in the execution artifact; a route change requires the probe result plus a populated `Deviation reason`. A missing wrapper, older failed run, or empty `.out` is indirect evidence and does not prove unavailability.
- Keep `Execution role` and `Assigned / replaced internal role` on separate lines. Do not merge them into one ambiguous label.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
- For `$external-worker` and `$external-reviewer`, the only valid execution path is the external CLI or a disabled-role outcome.
- `Actual execution path: internal subagent (provider-labeled)` is always invalid for external adapter roles and must be treated as a routing violation, not as partial success.
- If a run is blocked because the provider is unavailable, report that explicitly and let the orchestrator reroute.

## Terms and Abbreviations

- `agents-mode`: Orchestrarium operator configuration overlay for delegation, external provider routing, MCP use, and parallelism.
- `reserve`: symbolic supplemental read-only candidate for advisory/review lanes only; it is separate from primary providers and not valid for worker or mutating routes.
- `reserveResolver`: scalar `agents-mode` key that binds symbolic `reserve` to a concrete read-only resolver such as `claude-sonnet`, `claude-wrapper`, or `wrapper:<command>`.
- `CLI`: Command-Line Interface; a provider or tool invoked from a shell.
- `L00`: owner/control routing line in the release-backed `12 + 1` read; it is documented evidence but not an external provider profile lane.
- `MCP`: Model Context Protocol; protocol for exposing tools and resources to agent runtimes.
- `QA`: Quality Assurance; verification work for tests, regressions, and acceptance criteria.
- `12 + 1`: twelve external routing lines plus one owner/control line from the release-backed RF12 interpretation.
- `stdin`: standard input stream for a process.
- `WEAK MODEL / NOT RECOMMENDED`: repository classification for example-only providers excluded from production `auto` routing.
