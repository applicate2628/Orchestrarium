# External Worker & External Reviewer — Design Spec

**Date:** 2026-04-09
**Status:** Approved
**Scope:** Orchestrarium skill-pack routing canon across Codex, Claude Code, and Gemini CLI

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
       advisory.repo-understanding: [claude, codex, gemini]
       advisory.design-adr: [claude, codex, gemini]
       review.pre-pr: [claude, codex, gemini]
       review.performance-architecture: [claude, codex, gemini]
       worker.default-implementation: [codex, claude, gemini]
       worker.systems-performance-implementation: [codex, claude, gemini]
       worker.long-autonomous: [claude, codex, gemini]
       worker.ui-structural-modernization: [codex, claude, gemini]
       worker.ui-surgical-patch-cleanup: [codex, claude, gemini]
       worker.visual-icon-decorative: [codex, claude, gemini]
       review.visual: [claude, codex, gemini]
     gemini-crosscheck:
       advisory.repo-understanding: [claude, gemini, codex]
       advisory.design-adr: [claude, gemini, codex]
       review.pre-pr: [claude, gemini, codex]
       review.performance-architecture: [claude, codex, gemini]
       worker.default-implementation: [codex, claude, gemini]
       worker.systems-performance-implementation: [codex, claude, gemini]
       worker.long-autonomous: [claude, codex, gemini]
       worker.ui-structural-modernization: [codex, claude, gemini]
       worker.ui-surgical-patch-cleanup: [codex, claude, gemini]
       worker.visual-icon-decorative: [codex, claude, gemini]
       review.visual: [claude, codex, gemini]
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
   externalGeminiFallbackMode: auto
   externalClaudeProfile: opus-max
   ```

   - `consultantMode` — consultant-only mode: `external`, `internal`, `disabled`
   - `delegationMode` — `manual`, `auto`, or `force` team delegation
   - `parallelMode` — `manual`, `auto`, or `force` general helper parallelism across internal and external lanes
   - `mcpMode` — `auto` vs `force` MCP routing policy
   - `preferExternalWorker` — external-worker as default on eligible worker-side lanes
   - `preferExternalReviewer` — external-reviewer as default on `review` + `QA` stages
   - `externalProvider` — shared provider universe `auto`, `claude`, `codex`, or `gemini` for provider-backed consultant / adapter selection
   - `externalPriorityProfile` — active named provider-order profile used only when `externalProvider: auto`
   - `externalPriorityProfiles` — per-profile lane matrix with ordered provider lists; `balanced` stays the default and `gemini-crosscheck` is the recommended broader-Gemini second-opinion profile
   - `externalOpinionCounts` — per-lane number of distinct external opinions required under `externalProvider: auto`; not a global cap on helper multiplicity
   - `externalModelMode` — shared cross-provider model policy: `runtime-default` leaves the resolved provider on its runtime default model/profile, while `pinned-top-pro` starts on the strongest documented provider-native model/profile and allows one named same-provider fallback on retryable provider exhaustion
   - `externalGeminiFallbackMode` — when the resolved provider is Gemini and the model policy is pinned, `disabled` keeps `gemini-3.1-pro` only, `auto` allows one retry on `gemini-3-flash` only for quota/limit/capacity-style failures, and `force` starts on `gemini-3-flash` immediately
   - `externalClaudeApiMode` — when the resolved provider is Claude, `disabled` forbids the secret-backed Claude API path, `auto` allows one wrapper-backed retry after the allowed Claude CLI path is exhausted, and `force` uses that wrapper-backed path as the primary Claude transport immediately
   - `externalClaudeProfile` — Codex-line only optional Claude CLI execution profile: `sonnet-high` or `opus-max`
   - Each toggle is independent
   - Default full shape on first creation: `externalClaudeApiMode: auto`, `delegationMode: manual`, `parallelMode: auto`, `mcpMode: auto`, `preferExternalWorker: false`, `preferExternalReviewer: false`, `externalProvider: auto`, `externalPriorityProfile: balanced`, shipped `externalPriorityProfiles` including `balanced` and `gemini-crosscheck`, and `externalOpinionCounts` defaulting every documented lane to `1`; provider-specific workdir keys default to `neutral`; the shared model policy defaults to `externalModelMode: runtime-default`; Gemini fallback defaults to `externalGeminiFallbackMode: auto`; Codex also writes `externalClaudeProfile: opus-max`

3. **Dispatch protocol (platform-dependent)**

| Profile | Lane | `externalProvider: auto` priority |
|---------|---------|---------|
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

   `externalProvider: auto` is pack-neutral and resolves through the active named profile instead of a line-default provider mapping. Explicit self-provider selection is allowed only as an override for isolation, transport, profile, or an intentionally independent rerun. If a repository wants Gemini-first routing for visual lanes, express that through an explicit provider override or a repo-local custom profile; `gemini-crosscheck` is the named shipped profile for bringing Gemini into broader advisory and review second-opinion sets without changing the default worker and visual lane order.

4. **Common rules**
   - CLI availability check before dispatch (`which codex` / `where codex` on Claude Code, `claude` / `claude.exe` on Codex, `gemini` wherever Gemini is selected)
   - Under `externalModelMode: runtime-default`, keep the selected provider on its runtime default model/profile.
   - Under `externalModelMode: pinned-top-pro`, hard tasks start on the strongest documented provider-native path: `--model gpt-5.4 --reasoning-effort xhigh` (Codex), `opus-max` / `--model opus --effort max` (Claude CLI), or `--model gemini-3.1-pro` (Gemini CLI).
   - If Gemini is the selected provider and the model policy is pinned, honor `externalGeminiFallbackMode`: `disabled` keeps `gemini-3.1-pro` only, `auto` allows one retry on `gemini-3-flash` only for quota, limit, capacity, HTTP `429`, or `RESOURCE_EXHAUSTED`-style Gemini failures, and `force` starts on `gemini-3-flash` immediately. Neither mode counts as a provider switch.
   - On any line where the resolved provider is Claude, `externalClaudeApiMode: auto` keeps the installed Claude wrapper under `.claude/agents/scripts/invoke-claude-api.sh` or `.ps1` as the named secondary Claude transport after the allowed Claude CLI path is exhausted. That wrapper reads `SECRET.md`, exports the declared `ANTHROPIC_*` values, and launches plain `claude`. `force` starts on that path immediately. If requested but unavailable, disclose that dependency/config failure instead of pretending the Claude route completed.
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
     - **Requested provider:** `<internal | claude | codex | gemini>`
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
| Claude CLI is unauthenticated, or the repository intentionally carries auth in `.claude/SECRET.md` | Prefer the installed Claude API wrapper allowed by `externalClaudeApiMode` instead of repeatedly probing a plain `claude` command that cannot authenticate. |
| PowerShell Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.ps1`. It must remain compatible with Windows PowerShell 5.1 and PowerShell 7+, it accepts both `-PrintSecretPath` and `--print-secret-path`, and forwarded Claude flags should be passed after `--%`. |
| Bash / Git Bash Claude API transport | Use `.claude/agents/scripts/invoke-claude-api.sh`. It launches plain `claude`; if the active shell still cannot see the binary, set `CLAUDE_BIN` explicitly. |
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
- `externalProvider: auto | claude | codex | gemini` — use the shared provider universe; `auto` resolves through the active named profile, and any extra Gemini-first visual routing should be expressed through an explicit provider override or a repo-local custom profile instead of assumed hidden heuristics
- `externalPriorityProfile: balanced | gemini-crosscheck | <custom>` — select which ordered provider map `auto` uses
- `externalPriorityProfiles` — maintain the per-profile lane matrix; this is where Gemini can be promoted into broader advisory or review roles when one opinion is not enough
- `externalOpinionCounts` — raise specific lanes above `1` when the orchestrator should collect multiple independent external opinions
- `parallelMode` is the general fan-out rule for any helper lane; `externalOpinionCounts` and brigade semantics remain the external-specific overlay on top
- `externalModelMode: runtime-default | pinned-top-pro` — shared cross-provider model policy; `runtime-default` keeps provider runtime selection, while `pinned-top-pro` asks each provider for its strongest documented native path with one named same-provider fallback on retryable provider exhaustion
- `externalGeminiFallbackMode: disabled | auto | force` — when the resolved provider is Gemini and the model policy is pinned, control whether Gemini stays on `gemini-3.1-pro`, retries once on `gemini-3-flash`, or starts on `gemini-3-flash` immediately
- `externalClaudeApiMode: disabled | auto | force` — when the resolved provider is Claude, control whether the secret-backed Claude API path is forbidden, used as a secondary Claude transport, or used as the primary Claude transport
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
