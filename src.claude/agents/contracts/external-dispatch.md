# External Dispatch Contract

This contract defines the shared routing semantics for the standalone Claude pack's consultant toggle file and external adapters.

## Shared config file

- Canonical path: `.claude/.agents-mode`
- `agents-mode` is the only supported operator overlay surface on the Claude line.
- Full value-by-value operator semantics live in [../../../docs/agents-mode-reference.md](../../../docs/agents-mode-reference.md).

Supported canonical keys:

```yaml
consultantMode: external  # allowed: external | internal | disabled
delegationMode: manual  # allowed: manual | auto | force
mcpMode: auto  # allowed: auto | force
preferExternalWorker: true  # allowed: false | true
preferExternalReviewer: true  # allowed: false | true
externalProvider: auto  # allowed here: auto | codex | claude | gemini
externalPriorityProfile: balanced  # allowed: balanced | gemini-crosscheck | <repo-local profile>
externalPriorityProfiles: {}  # allowed: structured profile map
externalOpinionCounts: {}  # allowed: structured lane-count map
externalCodexWorkdirMode: neutral  # allowed: neutral | project
externalClaudeWorkdirMode: neutral  # allowed: neutral | project
externalGeminiWorkdirMode: neutral  # allowed: neutral | project
externalClaudeSecretMode: auto  # allowed when Claude is selected: auto | force
externalClaudeApiMode: auto  # allowed when Claude is selected: disabled | auto | force
```

Semantics:

- `consultantMode` continues to govern `$consultant`.
- `delegationMode: manual` keeps explicit user-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` lets the agent decide when available MCP tools are appropriate; `force` makes relevant MCP usage a standing explicit instruction.
- `preferExternalWorker` and `preferExternalReviewer` are routing preferences for eligible external adapter substitutions.
- `externalProvider` uses the shared provider universe `auto | codex | claude | gemini`.
- `externalProvider: auto` resolves by the active named priority profile and skips the current host provider. Explicit self-provider requests remain allowed when the user asks for them or when routing needs isolation, profile, or transport differences.
- `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`; missing means `balanced`.
- `externalPriorityProfiles` stores the ordered provider lists per lane for each named profile; the shipped profiles live in the shared operator reference.
- `externalOpinionCounts` stores how many distinct external opinions to collect per lane; missing entries mean `1`.
- `externalOpinionCounts` is a same-lane distinct-opinion contract, not a helper-multiplicity cap. It does not prevent repeated same-provider helper instances on different admitted artifacts or disjoint slices.
- `externalCodexWorkdirMode`, `externalClaudeWorkdirMode`, and `externalGeminiWorkdirMode` choose whether each provider-backed external run starts in a fresh neutral empty directory or in the current project/worktree. The ordinary default is `neutral`.
- `externalClaudeSecretMode` and `externalClaudeApiMode` are transport-only and apply only after the resolved provider is `claude`; `claude-api` is a secondary Claude transport, not a fourth provider.
- Any tool that updates the file must preserve unknown keys in place and must not rewrite the file back to a consultant-only shape.
- Any read of `.claude/.agents-mode` that influences routing must normalize an existing file to the current canonical format before trusting the flags. Comment-free or older-layout files are valid input, not valid output.
- When writing `.claude/.agents-mode`, keep each key on its own line and add an inline YAML comment that enumerates the allowed values for that key.
- Normalization preserves effective known values and unknown keys, fills missing canonical keys with current defaults, removes retired canonical keys, refreshes inline comments plus the shipped profile/count blocks, and restores canonical key order.
- If both files exist, `.claude/.agents-mode` wins.

## Named priority profiles

- `externalPriorityProfile` selects the named provider-order map used only when `externalProvider: auto`.
- `balanced` is the shipped default profile and must always exist.
- Repo-local heuristics may refine lane classification, but they must not invent a different provider universe.
- Ordinary `auto` must not resolve to the same provider as the current host line.

## Provider selection

- `externalProvider: auto` resolves by the active named priority profile and skips the current host provider.
- Explicit self-provider requests are allowed when the user asks for them or when routing needs isolation, profile, or transport differences.
- When the resolved provider is Codex, honor `externalCodexWorkdirMode`; when it is Claude, honor `externalClaudeWorkdirMode`; when it is Gemini, honor `externalGeminiWorkdirMode`.
- `externalClaudeSecretMode` and `externalClaudeApiMode` are transport-only and apply only after the resolved provider is `claude`; `claude-api` is a secondary Claude transport, not a fourth provider.
- When `externalClaudeApiMode` allows `claude-api`, prefer `.claude/agents/scripts/invoke-claude-api.sh` or `.claude/agents/scripts/invoke-claude-api.ps1` so the transport reads repo-local `.claude/SECRET.md` first and then `~/.claude/SECRET.md`. Fall back to a direct `claude-api` command only when the wrapper surface is unavailable.
- If the wrapper or direct `claude-api` transport is requested but unavailable, disclose that as a dependency/config failure.
- If the plain Claude CLI is selected but is clearly unauthenticated, prefer the allowed Claude API transport instead of repeatedly retrying a plain `claude` command that cannot log in.
- Use `.claude/agents/scripts/invoke-claude-api.ps1` from PowerShell and `.claude/agents/scripts/invoke-claude-api.sh` from Bash or Git Bash. The PowerShell wrapper must stay compatible with Windows PowerShell 5.1 and PowerShell 7+, and the Bash wrapper must honor `CLAUDE_API_BIN` when the shell PATH differs from PowerShell PATH.
- For wide release or parity audits, split the admitted scope by repo, file set, or lane instead of launching one mega neutral-dir prompt across the whole pack family.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must use direct external launch from the orchestrating runtime or an approved transport wrapper script. Do not proxy them through an internal agent/helper/subagent host.
- The adapter does not change the team template JSON.
- The adapter replaces an eligible internal role at routing time and keeps the replaced role label in provenance.
- If the external CLI is unavailable, the adapter is disabled and the orchestrator reroutes the work to another eligible path.
- The adapter itself must not silently fall back to an internal specialist.
- When multiple eligible external adapters are independent, they may run in parallel; if native internal slot limits would otherwise block independent eligible lanes, prefer available external adapters over silent serialization or dropping a lane.
- Same-provider external helper reuse is allowed when each run owns a different admitted artifact or disjoint slice; `externalOpinionCounts` remains a same-lane distinct-opinion contract, not a helper-multiplicity cap.
- When multiple independent external lanes should launch together, use the brigade surface so the batch has one explicit plan and one aggregated result surface.

## External worker

- `$external-worker` is the external worker-side adapter.
- It may stand in for any eligible non-owner, non-review role.
- The `Assigned role` provenance label names the internal implementer role being replaced.
- Implementation-side tasks stay implementation-side; the adapter does not take review or QA ownership.

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
| Owner roles such as `$product-manager` or `$lead` | unsupported | Fail fast before provider resolution. There is no generic external owner adapter. |

Rules:

- An explicit request for `external` does not create a new adapter type.
- Unsupported external role requests must stop with an unsupported-route explanation and an honest reroute suggestion instead of probing Codex or Gemini availability as if a missing adapter might exist.
- Worker-side specialist lanes such as `analyst`, `architect`, `planner`, `knowledge-archivist`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` remain eligible for `$external-worker` when routing selects external substitution.

## Provenance header

Every external-adapter artifact should include one explicit execution record with these separate fields:

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
- `internal consultant` is valid only for the consultant role when `consultantMode: internal`.
- `Requested provider: internal` means no explicit external provider was requested by the caller and routing/default resolution picked the provider. It must not be rendered as `auto` in the artifact.
- Provider-backed consultant execution in `external` mode plus `$external-worker` and `$external-reviewer` must show a direct external transport path. An internal agent/helper/subagent host means the route failed the contract and must be reported as disabled or rerouted.
- The adapter may replace an internal role for provenance, but the artifact must still show which role actually ran and which role was replaced.
