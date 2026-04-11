# Agents-Mode Reference

Canonical value-by-value operator reference for pack-local `agents-mode` files. Keep full `value | meaning` semantics here and let root manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surfaces

| Provider | Canonical file | Provider-specific note |
|---|---|---|
| Codex | `.agents/.agents-mode` | Shares the canonical provider universe `auto | codex | claude | gemini`. `auto` resolves by lane type through the active named profile below; explicit `codex` is a self-provider override only, never the ordinary `auto` result. Codex may additionally store `externalClaudeSecretMode`, `externalClaudeApiMode`, and `externalClaudeProfile` when the resolved provider is Claude. |
| Claude Code | `.claude/.agents-mode` | Shares the canonical provider universe `auto | codex | claude | gemini`. `auto` resolves by lane type through the active named profile below; explicit `claude` is a self-provider override only, never the ordinary `auto` result. `claude-api` remains a Claude transport, not a separate provider. |
| Gemini CLI | `.gemini/.agents-mode` | Shares the canonical provider universe `auto | codex | claude | gemini`. `auto` resolves by lane type through the active named profile below; explicit `gemini` is a self-provider override only, never the ordinary `auto` result. Official Gemini runtime config still lives in `.gemini/settings.json`; Orchestrarium install seeds the overlay, and Gemini `/init` still owns `GEMINI.md`. |

`agents-mode` is now the only supported operator overlay surface on all three lines.

The exemplar shared default lives in `shared/agents-mode.defaults.yaml`. In the monorepo, installers seed project-local and global `agents-mode` files directly from that shared exemplar while preserving existing files on reinstall; any provider-only additions are applied at install time instead of living in separate `src.<provider>/agents-mode.defaults.yaml` files. Standalone pack roots still ship one canonical pack-root seed file so those repositories remain self-contained outside the monorepo.

## Canonical maintenance

- Any tool or skill that reads an existing `agents-mode` file to make a routing or operator-mode decision must normalize that file to the current canonical format before trusting the flags.
- In the monorepo, edit only `shared/agents-mode.defaults.yaml`; do not reintroduce provider-local `src.<provider>/agents-mode.defaults.yaml` duplicates.
- Treat comment-free files, partially populated files, older layouts, and stale shipped profile blocks as legacy input that must be rewritten rather than preserved verbatim.
- Read-time normalization preserves the effective values of known keys, preserves unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline allowed-value comments, rewrites the shipped `externalPriorityProfiles` and `externalOpinionCounts` blocks to the current pack version, and restores canonical key order.
- This maintenance rewrite happens on read, not only on explicit toggle or init writes. A status-style read is still expected to leave the file in current canonical form after parsing.

## Shared keys

### `consultantMode`

| Value | Meaning | Ordinary optional consultant use | Mandatory batch-close external consultant-checks |
|---|---|---|---|
| `external` | External-only consultant | Use the selected external CLI only. If it is unavailable or fails, return an unavailable advisory memo and keep routing honest. | Do not downgrade to internal fallback. Return an unavailable advisory memo and keep the batch open for escalation. |
| `internal` | Internal-only consultant | Use the internal consultant path for ordinary optional second-opinion work. | Unavailable in this mode because the batch-close check is explicitly external. Keep the batch open for escalation. |
| `disabled` | Consultant disabled | Skip ordinary optional second-opinion use. | Unavailable in this mode. Return an unavailable advisory memo and keep the batch open for escalation. |

Notes:
- No config file behaves like consultant-disabled for ordinary optional consultant use.
- `consultantMode` governs consultant behavior only. It does not replace reviewer, QA, or human publication gates, and `external` never authorizes an internal fallback.
- The default closeout requirement follows the active lane policy's configured external consultant-check count. If a lane omits an explicit count, treat it as `1`.

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
| `claude` | Route provider-backed external work to Claude CLI | Valid wherever Claude CLI is installed. When this value is selected or `auto` resolves to Claude, honor `externalClaudeSecretMode` and `externalClaudeApiMode`; Codex may additionally honor `externalClaudeProfile`. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. If selected from the Codex line, treat it as an explicit self-provider override only. |
| `gemini` | Route provider-backed external work to Gemini CLI | Valid wherever Gemini CLI is installed. If selected from the Gemini line, treat it as an explicit self-provider override only. |

Notes:
- `externalProvider` selects the external CLI for provider-backed consultant, `$external-worker`, and `$external-reviewer` execution.
- If the selected provider is unavailable, the role does not pretend the same provider-backed run succeeded locally; the orchestrator must disclose the failure and reroute explicitly.
- Provider-backed consultant execution in `external` mode and both external adapter roles must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not satisfy that route by spawning an internal agent/helper/subagent host.
- `auto` uses the active named provider-order profile and must not silently self-bounce into the same provider line.
- Explicit self-provider selection is allowed only as an override for isolation, profile, transport, or an intentionally independent rerun.
- `claude-api` is a secondary Claude transport, not a fourth provider.
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
| `balanced` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > codex > gemini` |
|  | `review.pre-pr` | `claude > codex > gemini` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > codex > gemini` |
|  | `worker.visual-icon-decorative` | `gemini > claude > codex` |
|  | `review.visual` | `gemini > claude > codex` |
| `gemini-crosscheck` | `advisory.repo-understanding` | `claude > gemini > codex` |
|  | `advisory.design-adr` | `claude > gemini > codex` |
|  | `review.pre-pr` | `claude > gemini > codex` |
|  | `worker.default-implementation` | `codex > claude > gemini` |
|  | `worker.long-autonomous` | `claude > gemini > codex` |
|  | `worker.visual-icon-decorative` | `gemini > claude > codex` |
|  | `review.visual` | `gemini > claude > codex` |

Notes:
- `balanced` is the implicit default profile and should always be available.
- Repo-local heuristics may refine lane classification, but they must not invent a different provider universe.
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
- `externalOpinionCounts` is a same-lane opinion contract, not a global concurrency cap. It does not prevent the lead from running multiple same-provider helper instances in parallel on different disjoint lanes or slices.
- When a lane asks for `2+` opinions, treat that as a distinct-opinion requirement whenever the provider order and availability make that possible. Reusing one provider repeatedly does not satisfy the opinion count for that same lane unless a repo-local rule says otherwise.

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

### `externalClaudeSecretMode`

| Value | Meaning | Effective Claude CLI behavior |
|---|---|---|
| `auto` | Limit-triggered SECRET-backed retry | Start with the plain Claude command. If that call fails on quota, limit, or reset errors, rerun the same one-line Claude command once with `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` added to that command environment. |
| `force` | SECRET-backed primary Claude call | Apply the same `ANTHROPIC_*` values from the local Claude `SECRET.md` to the first Claude call immediately. Do not perform a second SECRET-backed retry because the primary call already used that environment override. |

Notes:
- This key is relevant whenever the resolved provider is Claude.
- `auto` is the first-write default where this key exists.
- If the required `ANTHROPIC_*` values cannot be read from the local Claude `SECRET.md`, disclose that explicitly. `force` must not silently fall back to a plain Claude call, and `auto` must not claim that the retry happened when it did not.
- This key changes only the Claude command environment. It does not authorize provider switches or profile downgrades.

### `externalClaudeApiMode`

| Value | Meaning | Effective Claude transport behavior |
|---|---|---|
| `disabled` | No Claude API transport | Use only the allowed Claude CLI path. If that path fails, Claude is unavailable. |
| `auto` | Claude CLI first, then `claude-api` fallback | Run the allowed Claude CLI path first, including any `externalClaudeSecretMode` retry semantics. If Claude still fails because of CLI availability, auth, quota, limit, or reset errors, retry once through the installed Claude wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` when that surface exists; otherwise fall back to the local `claude-api` command. |
| `force` | Claude API primary transport | Use the installed Claude wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` as the primary Claude transport when available; otherwise use `claude-api` directly and do not spend time on a preceding Claude CLI attempt. |

Notes:
- This key is relevant whenever the resolved provider is Claude.
- `auto` is the first-write default where this key exists.
- The preferred Claude API transport surface is the installed wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`, which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`.
- If that wrapper surface is unavailable, `claude-api` itself must still be available on PATH for `auto` fallback or `force` primary mode to succeed.
- This key selects transport, not provider. It does not authorize switching away from the resolved Claude provider.

## Practical launch rules

| Situation | Rule |
|---|---|
| Claude CLI is the chosen provider and is already authenticated | Use the plain Claude CLI path first. |
| Claude CLI is not logged in, or auth is intentionally repo-local | Prefer the installed Claude API wrapper allowed by `externalClaudeApiMode` instead of repeatedly probing a plain `claude` command that cannot authenticate. |
| PowerShell Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.ps1`. The wrapper must work on Windows PowerShell 5.1 and PowerShell 7+, and it accepts both `-PrintSecretPath` and `--print-secret-path`. |
| Bash / Git Bash Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.sh`. The wrapper resolves `claude-api`, `claude-api.cmd`, or `claude-api.exe`; if the active shell still cannot see the binary, set `CLAUDE_API_BIN` explicitly. |
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

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalCodexWorkdirMode` | `externalClaudeWorkdirMode` | `externalGeminiWorkdirMode` | `externalClaudeSecretMode` | `externalClaudeApiMode` | `externalClaudeProfile` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Codex | requested value | `manual` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `neutral` | `auto` | `auto` | `sonnet-high` unless explicitly overridden |
| Claude Code | requested value | `manual` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `neutral` | `auto` | `auto` | not part of canonical Claude-line config |
| Gemini CLI | requested value | `manual` | `auto` | `false` | `false` | `auto` | `neutral` | `neutral` | `neutral` | `auto` | `auto` | not part of canonical Gemini-line config |

Structured defaults written alongside the scalar keys:

| Key | Default |
|---|---|
| `externalPriorityProfile` | `balanced` |
| `externalPriorityProfiles` | ship `balanced` and `gemini-crosscheck` |
| `externalOpinionCounts` | all documented lanes default to `1` unless repo-local policy explicitly raises a lane |

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
| Same-provider fan-out | Parallel external work is not capped at one instance per helper or provider. Multiple simultaneous `consultant`, `external-worker`, or `external-reviewer` runs may target the same provider when each run owns a different admitted artifact or disjoint slice. |
| External adapter availability | `$external-worker` and `$external-reviewer` do not silently fall back inside the role. If the external CLI is unavailable, the adapter is disabled and the orchestrator reroutes explicitly. |
| Direct external launch | Provider-backed consultant execution in `external` mode and both external adapter roles must launch the selected external transport directly. If the host runtime cannot do that, the route is disabled rather than proxied through an internal helper. |
| External workdir mode | `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each external provider runs in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`. |
| Claude SECRET mode | `externalClaudeSecretMode: auto` keeps the limit-triggered retry path, while `force` applies the same `ANTHROPIC_*` environment to the primary Claude call. Both modes stay inside the Claude provider. |
| Claude API mode | `externalClaudeApiMode: auto` keeps Claude CLI first and then tries `claude-api` as the named secondary Claude transport; `force` starts on `claude-api` immediately. |
| Active priority profile | `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`. Unknown profile names fail closed. |
| Multi-opinion routing | `externalOpinionCounts` controls how many distinct external opinions a lane must collect under `auto`. Missing counts mean `1`; shortfalls keep the lane `BLOCKED`. |
| External brigade | A brigade is a bounded parallel set of external helper runs. It may mix providers or reuse one provider many times, but each brigade item still owns one execution role, one admitted artifact, and one gate. |
| Shared provider universe | All three packs use the same provider universe: `auto | codex | claude | gemini`. |
| Shared lane matrix | `externalProvider: auto` resolves by lane type through the active priority profile instead of by host pack identity. |
| Self-provider rule | Ordinary `auto` must not resolve to the same provider as the host line. Self-provider is explicit-override only. This is a repo-local routing rule, not an official provider-wide ban on invoking the same CLI. |
| Repo-local Gemini cross-check | In this repository, `gemini-crosscheck` is the named profile for bringing Gemini into broader non-visual advisory and review lanes when one independent opinion is not enough. |
| Repo-local visual heuristic | In this repository, image generation, icon work, and decorative visual polish prefer Gemini as the external provider when that routing remains honest and Gemini is installed. This preference applies to eligible worker-side lanes and visual review or advisory work. |
| Unknown keys | Tools that update `agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
