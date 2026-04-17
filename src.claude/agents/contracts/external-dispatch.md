# External Dispatch Contract

This contract defines the shared Claude-line routing semantics for the consultant toggle file and the external adapters.

## Shared config file

- Canonical path: `.claude/.agents-mode.yaml`
- Legacy `.claude/.agents-mode` is compatibility input only. Resolve Claude overlay state in this order: local `.claude/.agents-mode.yaml`, local legacy `.claude/.agents-mode`, global `~/.claude/.agents-mode.yaml`, then global legacy `~/.claude/.agents-mode`. Normalize whichever file supplied the effective config into the canonical `.yaml` path in the same scope, do not recreate any legacy file, and do not synthesize a local override on read alone.
- Full value-by-value operator semantics live in [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md).

Supported canonical keys:

```yaml
consultantMode: external  # allowed: external | internal | disabled; default: disabled
externalClaudeApiMode: auto  # allowed when Claude Code is the resolved provider for this run: disabled | auto | force; default: auto
delegationMode: manual  # allowed: manual | auto | force; default: manual
parallelMode: auto  # allowed: manual | auto | force; default: auto
mcpMode: auto  # allowed: auto | force; default: auto
preferExternalWorker: true  # allowed: false | true; default: false
preferExternalReviewer: true  # allowed: false | true; default: false
externalProvider: auto  # allowed here: auto | codex | claude | gemini; default: auto
externalPriorityProfile: balanced  # allowed: balanced | gemini-crosscheck | <repo-local profile>; default: balanced
externalPriorityProfiles: {}  # allowed: structured profile map
externalOpinionCounts: {}  # allowed: structured lane-count map
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalGeminiWorkdirMode: neutral  # allowed: neutral | project
externalModelMode: runtime-default  # allowed: runtime-default | pinned-top-pro; default: runtime-default
externalGeminiFallbackMode: auto  # allowed when Gemini CLI is the resolved provider for this run under pinned mode: disabled | auto | force; default: auto
```

Semantics:

- `consultantMode` continues to govern `$consultant`.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `parallelMode: manual` keeps ordinary parallel fan-out explicit-only, `auto` parallelizes safe independent lanes by routing judgment, and `force` makes safe parallel launch a standing instruction whenever scopes are independent and the merge cost is justified.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` and `preferExternalReviewer` are routing preferences for eligible external adapter substitutions.
- `externalProvider` uses the shared provider universe `auto | codex | claude | gemini`.
- `externalProvider: auto` resolves by lane type through the active named priority profile instead of by host-pack identity.
- `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`; missing means `balanced`.
- `externalPriorityProfiles` stores the ordered provider lists per lane for each named profile; the shipped profiles live in the shared operator reference.
- `externalOpinionCounts` stores how many distinct external opinions to collect per lane; missing entries mean `1`.
- `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each provider-backed external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalModelMode` is the shared cross-provider model policy. `runtime-default` leaves the resolved provider on its runtime default model/profile. `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion.
- `externalGeminiFallbackMode` matters only when the resolved provider is Gemini and the model policy is pinned. `disabled` keeps `gemini-3.1-pro` only, `auto` starts on `gemini-3.1-pro` and allows one retry on `gemini-3-flash` only for limit, quota, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures, and `force` starts on `gemini-3-flash` immediately.
- `externalClaudeApiMode` applies whenever the resolved provider is Claude. `disabled` forbids the repo-local secret-backed Claude API path, `auto` uses it after the allowed Claude CLI path is exhausted, and `force` uses that secret-backed path as the primary Claude transport. It remains a Claude transport, not a fourth provider.
- Treat named fallback paths as alternate limit or budget pools only when runtime observation shows they exhaust independently. That remains repo-local operator policy rather than an official provider guarantee.
- Claude-line does not use `externalClaudeProfile` as part of the canonical schema and should not write it into `.agents-mode.yaml`.
- Any tool that updates the file must preserve unknown keys in place and must not rewrite the file back to a consultant-only shape.
- Any read of the effective Claude overlay that influences routing must normalize that file to the current canonical format before trusting the flags. Comment-free or older-layout files are valid input, not valid output.
- If local `.claude/.agents-mode.yaml` is missing, read local legacy `.claude/.agents-mode` as compatibility input only; if both local files are missing, fall back to global `~/.claude/.agents-mode.yaml` and then global legacy `~/.claude/.agents-mode`. Normalize whichever file supplied the effective config in place before trusting the flags.
- When writing `.claude/.agents-mode.yaml`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.
- Explicit user override or documented repo-local task-domain heuristics may still rank Gemini first for image, icon, or decorative visual work over the ordinary `auto` result.

## Claude-line provider

- `externalProvider: auto` resolves by lane type through the active named priority profile instead of by host-pack identity.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`; when it is Gemini, honor `externalGeminiWorkdirMode`.
- Explicit `externalProvider: claude` is a self-provider override only. Ordinary `auto` must not silently self-bounce into Claude from the Claude line.
- `externalClaudeApiMode: auto` keeps the installed secret-backed Claude wrapper as the named secondary Claude transport after the allowed Claude CLI path is exhausted. `externalClaudeApiMode: force` starts on that wrapper path immediately and skips the preceding Claude CLI attempt.
- Treat the secret-backed wrapper as the approved economical near-full-strength Claude transport. `force` is therefore an explicit budget choice as well as a limit fallback.
- When `externalClaudeApiMode` allows the Claude API path, use the installed wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.claude/agents/scripts/invoke-claude-api.ps1` so the transport reads `ANTHROPIC_*` from repo-local `.claude/SECRET.md` first and then from `~/.claude/SECRET.md`, then launches plain `claude`.
- If that wrapper path is requested but unavailable, disclose that as a dependency/config failure.
- If the plain Claude CLI is selected but is clearly unauthenticated, prefer the allowed Claude API transport instead of repeatedly retrying a plain `claude` command that cannot log in.
- Use `.claude/agents/scripts/invoke-claude-api.ps1` from PowerShell and `.claude/agents/scripts/invoke-claude-api.sh` from Bash or Git Bash. The PowerShell wrapper must stay compatible with Windows PowerShell 5.1 and PowerShell 7+, forwarded Claude flags should be passed after `--%`, and the Bash wrapper must honor `CLAUDE_BIN` when the shell PATH differs from PowerShell PATH.
- On Windows, keep the ordinary external launch path unchanged and try the native Windows shell first. If that native shell path fails because of shell bootstrap, execution-policy, or environment-policy problems, retry once through Git-for-Windows Bash / MSYS when available. Do not use the WSL `bash.exe` stub as a fallback, and do not reinterpret ordinary provider auth, quota, or model failures as shell-fallback triggers.
- Treat `gpt-5.3-codex-spark` and `gemini-3-flash` as bounded mechanical overflow paths only when those providers resolve externally; they are not the ordinary cheaper mode for reasoning-heavy or cleanup-heavy work.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.
- The adapter does not change the team template JSON.
- The adapter replaces an eligible internal role at routing time and keeps the replaced role label in provenance.
- If the external CLI is unavailable, the adapter is disabled and the orchestrator may reroute the work to another eligible path.
- The adapter itself must not silently fall back to an internal specialist.
- `parallelMode` is the general orchestrator rule for whether independent helper lanes should be parallelized by judgment at all; external adapter fan-out is one overlay on top of that rule.
- Multiple external adapters may run in parallel when their scopes are independent, `parallelMode` permits ordinary parallel fan-out, and the selected provider runtimes support concurrent non-interactive execution.
- Do not cap that fan-out at one instance per helper or provider: the same external helper and the same resolved provider may be launched multiple times concurrently when each run owns a different admitted artifact or disjoint slice.
- `externalOpinionCounts` governs distinct-provider opinions for one lane; it does not replace the general `parallelMode` rule or forbid brigade-style reuse of the same provider across different independent lanes or slices.
- Same-provider external helper reuse is allowed when each run owns a different admitted artifact or disjoint slice.
- If internal native slot limits would otherwise block more independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.
- When multiple independent external lanes should launch together, prefer the operator surface `/agents-external-brigade` so the batch has one explicit brigade plan and one aggregated result surface. This is the dedicated brigade surface.

## External worker

- `$external-worker` is the external worker-side adapter.
- It may stand in for any eligible non-owner, non-review role.
- The `Assigned role` provenance label names the internal worker role being replaced.
- Worker-side tasks stay worker-side; the adapter does not take review or QA ownership.

## External reviewer

- `$external-reviewer` is the external review-side adapter.
- It may stand in for any eligible review or QA-side role.
- The `Assigned role` provenance label names the internal review-side role being replaced.
- Review-side tasks stay review-side; the adapter does not take implementation ownership.

## Eligibility gate

Resolve external dispatch in this order: `role eligibility -> provider selection -> CLI availability`.

| Requested role family | External path | Required result |
| --- | --- | --- |
| Advisory second opinion | `$consultant` | Advisory-only. Never becomes a worker or review lane. |
| Eligible worker-side role | `$external-worker` | Valid only after routing has already classified the work as non-owner, non-review work. This includes research, design, planning, scientist or constraint, implementation, and repository-hygiene roles. |
| Eligible review or QA-side role | `$external-reviewer` | Valid only after routing has already classified the work as review or QA. |
| Owner roles such as `$product-manager` or `$lead` | unsupported | Fail fast before provider resolution. There is no generic external owner adapter on the Claude line. |

Rules:

- An explicit request for `external` does not create a new adapter type.
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing Codex, Claude, or Gemini availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution.

## Named priority profiles

- `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`.
- `balanced` is the shipped default profile and must always exist.
- Repo-local heuristics may refine lane classification, but they must not invent a different provider universe.
- Ordinary `auto` must not resolve to the same provider as the current host line.

## Provenance header

Every external or consultant artifact should include one explicit execution record with these separate fields:

- `Execution role: <consultant | external-worker | external-reviewer>`
- `Assigned / replaced internal role: <eligible internal role label | none>`
- `Requested provider: <internal | codex | claude | gemini>`
- `Resolved provider: <Codex CLI | Claude CLI | Gemini CLI | none>`
- `Requested consultant mode: <external | internal | disabled>` when consultant routing is relevant; otherwise `not-applicable`
- `Actual execution path: <internal consultant | external CLI (Codex CLI) | external CLI (Claude CLI) | external CLI (Gemini CLI) | role disabled>`
- `Model / profile used: <actual profile or model when known | runtime default | unspecified by runtime>`
- `Deviation reason: <none | external unavailable: [reason]>`

Rules:

- Keep `Execution role` and `Assigned / replaced internal role` on separate lines. Do not merge them into one ambiguous label.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
- The adapter may replace an internal role for provenance, but the artifact must still show which role actually ran and which role was replaced.
