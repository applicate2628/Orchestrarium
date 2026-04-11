# Agents-Mode Reference

Canonical value-by-value operator reference for the standalone Claude Code pack. Keep the shared provider universe, active named priority-profile semantics, self-provider rule, Claude transport semantics, and neutral workdir defaults here; let root manuals or provider contracts link here instead of duplicating the same tables in multiple places.

## Provider surface in this branch

| Provider | Canonical file | Provider-specific note |
|---|---|---|
| Claude Code | `.claude/.agents-mode` | Shared provider universe: `auto | codex | claude | gemini`. `auto` resolves by lane type through the active named priority profile and skips the current host provider. `claude-api` is a Claude transport, not a fourth provider. Installs seed the default file into the active target and preserve existing overlays on reinstall. |

Tooling should read and write only `.claude/.agents-mode`.

## Canonical maintenance

- Any tool or skill that reads an existing `.claude/.agents-mode` file to make a routing or operator-mode decision must normalize that file to the current canonical format before trusting the flags.
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
| `auto` | Resolve by lane type using the active named priority profile, then skip the current host provider | This keeps routing host-neutral and avoids silent self-bounce. |
| `codex` | Route provider-backed external work to Codex CLI | Valid wherever Codex CLI is installed. |
| `claude` | Route provider-backed external work to Claude CLI | Valid wherever Claude CLI is installed and the user explicitly asked for a Claude target. |
| `gemini` | Route provider-backed external work to Gemini CLI | Valid wherever Gemini CLI is installed. |

Notes:
- `auto` is lane-driven, not host-default-driven.
- Explicit self-provider requests are allowed when the user asks for them or when routing needs isolation, profile, or transport differences.
- `claude-api` is transport-only and applies only after the resolved provider is `claude`.

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

### `externalOpinionCounts`

| Value | Meaning | Expected behavior |
|---|---|---|
| omitted or `1` | Single external opinion | Keep current single-provider behavior after the provider order resolves. |
| `2+` | Multi-opinion fan-out on the lane | Walk the ordered provider list, skip unavailable providers and ordinary self-bounce, and collect distinct eligible external opinions until the requested count is satisfied or fail closed. |

Notes:
- Missing `externalOpinionCounts[lane]` means `1`.
- Multi-opinion fan-out applies only when `externalProvider: auto`.
- If the requested opinion count cannot be satisfied from the resolved provider order, the lane stays `BLOCKED`; partial collection is evidence, not success.
- `externalOpinionCounts` is a same-lane distinct-opinion contract, not a helper-multiplicity cap. It does not prevent the lead from running multiple same-provider external helpers in parallel on different disjoint lanes or slices.
- When multiple independent external lanes should launch together, use `/agents-external-brigade` so the batch has one explicit brigade plan and one aggregated result surface.

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
- These keys are provider-specific execution-directory policies, not provider selectors.
- `neutral` is the first-write default for all three keys.
- The ordinary default should be a neutral empty directory so comparative or external runs do not accidentally inherit repo-local instruction overlays by cwd alone.
- When the resolved provider is `codex`, honor `externalCodexWorkdirMode`; when it is `claude`, honor `externalClaudeWorkdirMode`; when it is `gemini`, honor `externalGeminiWorkdirMode`.

### Claude transport

#### `externalClaudeSecretMode`

| Value | Meaning | Effective Claude CLI behavior |
|---|---|---|
| `auto` | Limit-triggered SECRET-backed retry | Start with the plain Claude command. If that call fails on quota, limit, or reset errors, rerun the same one-line Claude command once with `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, and `ANTHROPIC_AUTH_TOKEN` from the local Claude `SECRET.md` added to that command environment. |
| `force` | SECRET-backed primary Claude call | Apply the same `ANTHROPIC_*` values from the local Claude `SECRET.md` to the first Claude call immediately. Do not perform a second SECRET-backed retry because the primary call already used that environment override. |

#### `externalClaudeApiMode`

| Value | Meaning | Effective Claude transport behavior |
|---|---|---|
| `disabled` | No Claude API transport | Use only the allowed Claude CLI path. If that path fails, Claude is unavailable. |
| `auto` | Claude CLI first, then `claude-api` fallback | Run the allowed Claude CLI path first, including any `externalClaudeSecretMode` retry semantics. If Claude still fails because of CLI availability, auth, quota, limit, or reset errors, retry once through `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` when that wrapper surface exists; otherwise fall back to the local `claude-api` command. |
| `force` | Claude API primary transport | Use `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` as the first Claude transport when that wrapper surface exists; otherwise use `claude-api` directly and do not spend time on a preceding Claude CLI attempt. |

Notes:
- These keys are transport-only and apply only after the resolved provider is `claude`.
- The preferred Claude API transport surface is `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1`, which reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`.
- `claude-api` remains the named secondary Claude transport behind that wrapper, not a fourth provider.

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

## Named priority profiles

| Lane | Priority |
|---|---|
| `advisory.repo-understanding` | `claude > gemini > codex` |
| `advisory.design-adr` | `claude > codex > gemini` |
| `review.pre-pr` | `claude > codex > gemini` |
| `worker.default-implementation` | `codex > claude > gemini` |
| `worker.long-autonomous` | `claude > codex > gemini` |
| `worker.visual-icon-decorative` | `gemini > claude > codex` |
| `review.visual` | `gemini > claude > codex` |

## Self-provider rule

| Case | Rule |
|---|---|
| Ordinary `auto` routing | Must not resolve to the same provider as the current host line. This is a repo-local routing rule, not an official provider-wide ban on invoking Claude from Claude. |
| Explicit self-provider request | Allowed if the user explicitly asks, or if routing needs profile, transport, or isolation differences. |
| Silent self-bounce | Forbidden. |
| Owner roles | Still unsupported for generic externalization. |
| Claude transport | `externalClaudeSecretMode` and `externalClaudeApiMode` apply only after provider already resolved to `claude`. |

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

## First-write defaults

| Provider | `consultantMode` | `delegationMode` | `mcpMode` | `preferExternalWorker` | `preferExternalReviewer` | `externalProvider` | `externalPriorityProfile` | `externalPriorityProfiles` | `externalOpinionCounts` | `externalCodexWorkdirMode` | `externalClaudeWorkdirMode` | `externalGeminiWorkdirMode` | `externalClaudeSecretMode` | `externalClaudeApiMode` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Claude Code | requested value | `manual` | `auto` | `false` | `false` | `auto` | `balanced` | shipped `balanced` + `gemini-crosscheck` | all documented lanes default to `1` | `neutral` | `neutral` | `neutral` | `auto` | `auto` |

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
| Active priority profile | `externalProvider: auto` resolves by lane type through the active named priority profile and skips the current host provider. On this line that means image/icon/decorative lanes may still prefer Gemini, but only when the active profile or an honest repo-local heuristic ranks it first. |
| Claude transport | `externalClaudeSecretMode` and `externalClaudeApiMode` are transport-only and apply only after the resolved provider is `claude`; `claude-api` is a secondary transport, not a provider. |
| Unknown keys | Tools that update `.claude/.agents-mode` should preserve unknown keys and keep the file in expanded multi-key form rather than collapsing it back to a consultant-only shape. |
| Read-time normalization | Readers must normalize an existing `.claude/.agents-mode` file to the current canonical format before trusting its flags. |
