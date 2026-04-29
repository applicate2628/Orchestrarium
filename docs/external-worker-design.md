# External Worker & External Reviewer — Design Spec

**Date:** 2026-04-09
**Status:** Approved
**Scope:** Orchestrarium skill-pack routing canon across the production Codex/Claude core plus explicit example integrations

**2026-04-28 production note:** Shipped production `externalProvider: auto` routing is now limited to `codex | claude`. Gemini CLI and Qwen remain explicit example integrations, both classified here as `WEAK MODEL / NOT RECOMMENDED`, and they do not participate in the shipped production profiles or production-only provider fallback/workdir schema.

## Problem

The current role architecture has no universal implementer or reviewer that works through an external CLI provider. Every implementation task requires selecting a domain-specific specialist (backend-engineer, frontend-engineer, etc.), even when the task is simple/mechanical or the external CLI is better suited. There is no "economy mode" toggle to prefer external dispatch for cost or workflow reasons.

## Decision

Introduce two new roles and a shared dispatch module:

- `$external-worker` — universal worker-side adapter via external CLI
- `$external-reviewer` — universal reviewer/QA via external CLI
- `external-dispatch.md` — shared CLI dispatch protocol (DRY, used by consultant + both new roles)

## New roles

### `$external-worker`

| Property | Value |
|----------|-------|
| File | `src.claude/agents/external-worker.md` |
| Stages | full worker-side lane |
| Replaces | Any eligible non-owner, non-review role, including research, design, planning, specialist-constraint, implementation, and repository-hygiene lanes |
| Interaction type | `DIRECT` (standard worker-side role) |
| Input contract | Accepted upstream artifacts and the assigned internal worker-role label — same as the replaced role |
| Output contract | Role-appropriate worker artifact + standard gate (`PASS \| REVISE \| BLOCKED`) |
| Execution | External CLI dispatch only. No internal fallback. If CLI unavailable — role is disabled. |
| Domain scope | Unrestricted. Works in any domain — determined by the task. |

### `$external-reviewer`

| Property | Value |
|----------|-------|
| File | `src.claude/agents/external-reviewer.md` |
| Stages | `review` + `QA` |
| Replaces | Domain-specific reviewers (architecture-reviewer, performance-reviewer, security-reviewer, ux-reviewer, accessibility-reviewer, ui-test-engineer) + qa-engineer |
| Interaction type | `DIRECT` (standard reviewer) |
| Input contract | Implementation artifact from the implement stage |
| Output contract | Review findings / QA verdict + standard gate (`PASS \| REVISE \| BLOCKED`) |
| Execution | External CLI dispatch only. No internal fallback. If CLI unavailable — role is disabled. |
| Separation of concerns | Worker implements, reviewer verifies. No conflict of interest. |

## Shared dispatch module

### File

| Pack | Path |
|------|------|
| Claude Code | `src.claude/agents/contracts/external-dispatch.md` |
| Codex | Corresponding location in `src.codex/` (e.g., `skills/lead/external-dispatch.md`) |

### Consumers

- `consultant.md` — refactored to reference this module instead of inline dispatch
- `external-worker.md` — references this module
- `external-reviewer.md` — references this module

### Contents

Full value-by-value operator semantics now live in [`agents-mode-reference.md`](agents-mode-reference.md). Keep this design spec at the decision level and let the dedicated reference own the complete `value | meaning` tables.

1. **Config file location**

   | Platform | Path |
   |----------|------|
   | Claude Code | `.claude/.agents-mode.yaml` |
   | Codex | `.agents/.agents-mode.yaml` |

2. **Extended config format**

   ```
   consultantMode: external
   externalClaudeApiMode: auto
   delegationMode: manual
   parallelMode: auto
   mcpMode: auto
   preferExternalWorker: true
   preferExternalReviewer: true
   externalProvider: auto
   externalPriorityProfile: balanced
   externalPriorityProfiles:
     balanced:
       advisory.repo-understanding: [claude, codex]
       advisory.design-adr: [claude, codex]
       review.pre-pr: [claude, codex]
       review.performance-architecture: [claude, codex]
       worker.default-implementation: [codex, claude]
       worker.systems-performance-implementation: [codex, claude]
       worker.long-autonomous: [claude, codex]
       worker.ui-structural-modernization: [codex, claude]
       worker.ui-surgical-patch-cleanup: [codex, claude]
       worker.visual-icon-decorative: [codex, claude]
       review.visual: [claude, codex]
   externalOpinionCounts:
     advisory.repo-understanding: 1
     advisory.design-adr: 1
     review.pre-pr: 1
     review.performance-architecture: 1
     worker.default-implementation: 1
     worker.systems-performance-implementation: 1
     worker.long-autonomous: 1
     worker.ui-structural-modernization: 1
     worker.ui-surgical-patch-cleanup: 1
     worker.visual-icon-decorative: 1
     review.visual: 1
   externalModelMode: runtime-default
   externalClaudeProfile: opus-max
   ```

   - `consultantMode` — consultant-only mode: `external`, `internal`, `disabled`
   - `delegationMode` — `manual`, `auto`, or `force` team delegation
   - `parallelMode` — `manual`, `auto`, or `force` general helper parallelism across internal and external lanes
   - `mcpMode` — `auto` vs `force` MCP routing policy
   - `preferExternalWorker` — external-worker as default on eligible worker-side lanes
   - `preferExternalReviewer` — external-reviewer as default on `review` + `QA` stages
   - `externalProvider` — shipped production provider universe `auto`, `claude`, or `codex` for provider-backed consultant / adapter selection
   - `externalPriorityProfile` — active named provider-order profile used only when `externalProvider: auto`
   - `externalPriorityProfiles` — per-profile lane matrix with ordered provider lists; the shipped production profile set stays on Codex plus Claude only
   - `externalOpinionCounts` — per-lane number of distinct external opinions required under `externalProvider: auto`; not a global cap on helper multiplicity
   - `externalModelMode` — shared production model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion
   - `externalClaudeApiMode` — controls the supplemental `claude-secret` candidate for advisory/review lanes; it does not turn a primary `claude` route into a wrapper-backed run and is not available to worker-side implementation/editing lanes
   - `externalClaudeProfile` — Codex-line only optional Claude CLI execution profile: `sonnet-high` or `opus-max`
   - Each toggle is independent
   - Default full shape on first creation: `externalClaudeApiMode: auto`, `delegationMode: manual`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles` on the Codex/Claude pair, and `externalOpinionCounts` defaulting every documented lane to `1`; provider-specific workdir keys default to `neutral`; the shared model policy defaults to `externalModelMode: runtime-default`; Codex also writes `externalClaudeProfile: opus-max`

3. **Dispatch protocol (platform-dependent)**

| Profile | Lane | `externalProvider: auto` priority |
|---------|---------|---------|
| `balanced` | `advisory.repo-understanding` | `claude > codex` |
|  | `advisory.design-adr` | `claude > codex` |
|  | `review.pre-pr` | `claude > codex` |
|  | `review.performance-architecture` | `claude > codex` |
|  | `worker.default-implementation` | `codex > claude` |
|  | `worker.systems-performance-implementation` | `codex > claude` |
|  | `worker.long-autonomous` | `claude > codex` |
|  | `worker.ui-structural-modernization` | `codex > claude` |
|  | `worker.ui-surgical-patch-cleanup` | `codex > claude` |
|  | `worker.visual-icon-decorative` | `codex > claude` |
|  | `review.visual` | `claude > codex` |

   `externalProvider: auto` is pack-neutral and resolves through the active named profile instead of a line-default provider mapping, but the shipped production profile remains limited to Codex plus Claude. Explicit self-provider selection is allowed only as an override for isolation, transport, profile, or an intentionally independent rerun. Gemini and Qwen remain `WEAK MODEL / NOT RECOMMENDED` example-only routes outside this production profile table.

4. **Common rules**
   - CLI availability check before dispatch (`which codex` / `where codex` on Claude Code, `claude` / `claude.exe` on Codex)
   - Under `externalModelMode: runtime-default`, keep the selected provider on its runtime default model/profile.
   - Under `externalModelMode: pinned-top-pro`, hard tasks start on the strongest documented production provider-native path: `--model gpt-5.4 --reasoning-effort xhigh` (Codex) or `opus-max` / `--model opus --effort max` (Claude CLI). Example-provider model behavior stays provider-local and is intentionally outside this production design spec.
   - On advisory and review lanes, `externalClaudeApiMode: auto` enables the installed Claude wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` as the supplemental `claude-secret` profile candidate after primary candidates such as `claude` and `codex`. That wrapper reads `SECRET.md`, exports the declared `ANTHROPIC_*` values, and launches plain `claude`. The wrapper is independent of primary `claude`; it is not a retry path for primary Claude and is unavailable for worker-side implementation, code-generation, file-editing, installer, publication, or write-producing repository-hygiene routes.
   - `externalPriorityProfile` selects the named provider-order map only when `externalProvider: auto`; unknown profile names fail closed instead of silently falling back.
   - `externalOpinionCounts` controls how many distinct external opinions a lane must collect under `auto`. Missing counts mean `1`; shortfalls keep the lane `BLOCKED`.
   - Reusing the same provider across multiple different brigade items is allowed when the scopes are independent; that is separate from satisfying one lane's distinct-opinion requirement.
   - Multi-opinion advisory or review lanes aggregate fail-closed: any returned `REVISE` or `BLOCKED` verdict blocks progression unless a stricter repo-local rule overrides it explicitly.
   - Timeout: 5-15 minutes before treating a run as stalled
   - Independent eligible external lanes may run in parallel when their scopes do not overlap and the selected provider runtimes support concurrent non-interactive execution.
   - If native internal slot limits would otherwise block additional independent eligible lanes, prefer the available external adapters instead of silently serializing or dropping them.
   - Execution record mandatory for all three roles:
     - **Execution role:** `<consultant | external-worker | external-reviewer>`
     - **Assigned / replaced internal role:** `<eligible internal role label | none>`
     - **Requested provider:** `<internal | claude | codex>`
     - **Resolved provider:** `<provider selected after routing/default resolution | none>`
     - **Actual execution path:** `<internal consultant | external CLI (provider name) | role disabled | role-play (violation)>`
     - **Model / profile used:** `<actual profile or model when known | runtime default | unspecified by runtime>`
     - **Deviation reason:** `<none | external unavailable: [reason]>`
   - Provider-backed consultant execution in `external` mode and both external adapter roles must use direct external launch from the orchestrating runtime or an approved transport wrapper script. If the host runtime cannot launch the selected provider directly, the route is `role disabled`.
   - Reporting rule: if the operator or caller left provider selection at runtime default behavior, artifacts must record `Requested provider: internal` and put the real provider choice in `Resolved provider`; do not emit `auto` in the execution record.

### Practical launch rules

| Situation | Rule |
|---|---|
| Claude CLI is selected and already authenticated | Use the plain Claude CLI path first. |
| Claude CLI is unauthenticated, or the repository intentionally carries auth in `.claude/SECRET.md` | Do not convert a primary `claude` route into a wrapper-backed run. Advisory/review lanes may still reach the independent `claude-secret` candidate later in the profile order when enabled. |
| PowerShell Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.ps1`. It must remain compatible with Windows PowerShell 5.1 and PowerShell 7+, it accepts both `-PrintSecretPath` and `--print-secret-path`, and forwarded Claude flags should be passed after `--%`. |
| Bash / Git Bash Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.sh`. It launches plain `claude`; if the active shell still cannot see the binary, set `CLAUDE_BIN` explicitly. |
| External provider CLI prompt payload | Write the substantive task prompt to a temporary prompt file and feed it through stdin or the provider's supported file-input mechanism. Keep argv for launcher flags, model/profile options, and file paths; inline prompt strings are only for tiny smoke checks or a documented provider limitation, and the deviation must be recorded. |
| Codex commit review transport | Use `codex review --commit <sha>` without a free-form prompt. If custom review instructions are needed, prefer a narrower `codex exec` run on the admitted scope instead of mixing text with `review --commit`. |
| Wide release or parity audits | Split by admitted repo, file set, or lane. Do not default to one mega neutral-dir prompt over the whole pack family because Codex and Gemini are more likely to stall on ultra-wide review scopes. |
| Neutral workdir default | Keep `external<Provider>WorkdirMode: neutral` unless the external run truly needs in-place filesystem execution or repo-local instruction surfaces, and always pass the exact repo, commit, file, or artifact scope explicitly. |

## Routing rules

### When toggles are ON

The orchestrator (lead or main conversation) **prefers** external roles by default:

- `consultantMode: external | internal | disabled` — consultant-only behavior
- `delegationMode: manual | auto | force` — `manual` keeps explicit-request behavior, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist
- `parallelMode: manual | auto | force` — `manual` keeps ordinary parallel fan-out explicit-only, `auto` parallelizes safe independent lanes by routing judgment, and `force` makes safe parallel launch a standing instruction across internal and external helper lanes
- `mcpMode: auto | force` — `auto` uses MCP by judgment; `force` treats relevant MCP use as an explicit standing instruction
- `preferExternalWorker: true` — `$external-worker` on eligible worker-side lanes
- `preferExternalReviewer: true` — `$external-reviewer` on eligible `review` + `QA` stages
- `externalProvider: auto | claude | codex` — use the shipped production provider universe; `auto` resolves through the active named profile, while example-provider routing stays explicit-only and outside the production profile set
- `externalPriorityProfile: balanced | <custom>` — select which ordered provider map `auto` uses
- `externalPriorityProfiles` — maintain the per-profile lane matrix; the shipped production profiles stay on the Codex/Claude pair
- `externalOpinionCounts` — raise specific lanes above `1` when the orchestrator should collect multiple independent external opinions
- `parallelMode` is the general fan-out rule for any helper lane; `externalOpinionCounts` and brigade semantics remain the external-specific overlay on top
- `externalModelMode: runtime-default | pinned-top-pro` — shared production model policy; `runtime-default` keeps provider runtime selection, while `pinned-top-pro` asks each production provider for its strongest documented native path with one named same-provider fallback on retryable provider exhaustion
- `externalClaudeApiMode: disabled | auto | force` — control whether the advisory/review-only `claude-secret` supplemental candidate is forbidden or available; it is independent of primary `claude` and not available to worker or mutating routes
- `externalClaudeProfile: sonnet-high | opus-max` — Codex-line only; when Codex dispatches to Claude CLI, prefer the matching model/effort profile instead of the provider default or the broader shared model policy

Domain specialist is selected instead only when:

1. Task objectively requires deep domain expertise (algorithms, geometry, security-sensitive)
2. Template **mandates** a specific reviewer (e.g., `security-reviewer` in `security-sensitive` template — safety gate, not replaceable)
3. Orchestrator explicitly justifies the choice

### When toggles are OFF

Standard behavior. External roles available only by explicit user request.

### Selection criteria for orchestrator

| Criterion | Route to |
|-----------|----------|
| Task is simple / mechanical | `$external-worker` / `$external-reviewer` |
| External CLI better suited for the task | `$external-worker` / `$external-reviewer` |
| User explicitly requested | `$external-worker` / `$external-reviewer` |
| Deep domain expertise required | Domain specialist |

### User override

Always available in both directions, regardless of toggle state.

### CLI unavailable

Normal routing fallback to domain specialist. Not an error — standard routing behavior.

## Affected files

| File | Change |
|------|--------|
| `src.claude/agents/external-worker.md` | **New** — worker-side external adapter role |
| `src.claude/agents/external-reviewer.md` | **New** — reviewer/QA role |
| `src.claude/agents/contracts/external-dispatch.md` | **New** — shared CLI dispatch |
| `src.claude/agents/consultant.md` | **Refactor** — inline CLI dispatch replaced with reference to external-dispatch.md |
| `src.claude/CLAUDE.md` | **Update** — role index + routing rules + delegation decision tree |
| `src.claude/agents/contracts/operating-model.md` | **Update** — routing rules for external roles |
| `src.claude/agents/contracts/subagent-contracts.md` | **Update** — mention new roles |
| Team templates (JSON) | **No change** — substitution via routing decision, not template entries |
| `src.codex/` (mirror) | **Analogous changes** — external-worker SKILL.md, external-reviewer SKILL.md, dispatch protocol, consultant refactor, governance updates |
| `src.gemini/` (mirror) | **Analogous changes** — external-worker surfaces, external-reviewer surfaces, dispatch protocol, and governance updates |

## Constraints

- `$external-worker` and `$external-reviewer` must never be the same agent instance on the same task (separation of concerns)
- Mandatory reviewers in risk-sensitive templates (`security-reviewer` in `security-sensitive`, `performance-reviewer` in `performance-sensitive`) are NOT replaceable by `$external-reviewer`
- No internal agent/helper/subagent host for provider-backed external roles — either direct external transport works or the role is disabled
- Explicit self-provider selection is override-only; ordinary `auto` must not silently self-bounce into the same host provider line
- The retired consultant-only overlay fallback is removed. Operator state must live only in the canonical `agents-mode` file for the current provider line, and validation should fail residual retired-overlay references instead of silently migrating them.

## Non-goals

- Changing team template JSON structure
- Replacing the consultant's advisory-only contract
- Adding new interaction types to the operating model
- Auto-detection of when external worker is "better" — orchestrator uses explicit criteria
