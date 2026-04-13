# Operating Model Reference

Reference for routing, interaction types, periodic controls, and role aliases. Read on demand.

## Isolation rule

**Every role invocation MUST use the Agent tool** with the matching `subagent_type`. Do not simulate roles in the main conversation or emulate a specialist by "acting as" that role. Each agent runs in its own isolated context and receives only the artifacts it needs.

- This applies to both `requiresLead: false` chains (main conversation invokes Agent tool per stage) and `requiresLead: true` chains (lead invokes Agent tool per specialist).
- Independent roles (e.g., `security-engineer` and `performance-engineer`) SHOULD be launched in parallel via multiple Agent tool calls in a single message.
- Sequential dependencies (e.g., `architect` → `planner`) MUST wait for the previous agent to return its artifact before launching the next.

## Template-based routing

Team templates in `.claude/agents/team-templates/` define the team composition and execution chain for each task type.

- Templates with `requiresLead: false` — main conversation manages the chain directly, invoking each specialist via Agent tool in stage order and passing accepted artifacts to the next.
- Templates with `requiresLead: true` — `$lead` (itself invoked via Agent tool) coordinates work-items, risk owners, integration, and gates, invoking each specialist via Agent tool.
- Re-classify immediately if scope widens beyond the current template.

## Routing principles

When lead coordinates, or when the main conversation needs to decide between roles within a template:

1. **Risk owners trigger reviewers**: if a specialist constraint role participated in design, add the corresponding reviewer after QA.
2. **UX lane**: if user-facing interaction design is needed, add `ux-designer` in design and `ux-reviewer` after QA.
3. **Parallel read-only**: research roles (analyst, product-analyst) can run in parallel. Write-heavy roles need explicit ownership boundaries.
4. **Re-intake**: if the admitted item itself changed materially, route back to `product-manager`. Cap: 2 re-intakes; on the 3rd, escalate to user with all prior re-intake reasons and ask for a final decision (reduce scope, defer, or cancel).

## Interrupted handoff recovery

- A handoff interrupt or worker stall without an artifact is not a completed `REVISE` artifact.
- Record the interruption in `status.md`, keep the stage open, and either re-dispatch the same role with a narrower slice or route to the proper factual role.
- The lead must not synthesize the missing artifact or replace missing factual work inline.
- On resume after interruption, restore only lead-owned task-memory state from persisted accepted artifacts. Do not reconstruct missing specialist artifacts or factual findings from chat memory.

## Primary-task lock

- Maintain exactly one primary in-progress task at a time.
- Side requests may refine or temporarily interrupt the primary task, but do not replace it unless the user explicitly reprioritizes.
- After handling a side request, explicitly resume the primary task and record the next concrete step before doing unrelated work.
- When interrupting non-trivial work, record a durable resume point: current stage, last accepted artifact, next concrete step, and open obligations before switching away.
- Before marking a batch or final answer complete, reconcile the current result against the original request, accepted scope, required checks, canonical-source updates, and any open obligations.
- Do not treat a partial sub-batch as completion when a known required next action still exists inside the admitted scope.
- A full-impact review or verification pass remains open until a review artifact is produced; side clarification may refine the review, but does not close or replace it.
- Do not begin install validation, commit, push, publication, or equivalent closeout work while a primary review or verification task remains open unless the user explicitly parks, cancels, or reprioritizes that task.

## External adapter routing

Claude-line keeps one shared local config file at `.claude/.agents-mode.yaml`.

- `consultantMode` continues to govern `$consultant`.
- `delegationMode: manual` keeps delegation explicit-by-request, `auto` leaves ordinary delegation enabled by routing judgment, and `force` makes delegation a standing instruction whenever a matching specialist and viable tool path exist.
- `mcpMode: auto` allows MCP use by judgment when appropriate; `force` makes relevant MCP use an explicit standing instruction.
- `preferExternalWorker: true` prefers `$external-worker` for eligible worker-side slots.
- `preferExternalReviewer: true` prefers `$external-reviewer` for eligible review and QA-side slots.
- `externalProvider: auto` resolves by the active named priority profile instead of a host-line default; explicit `codex`, `claude`, or `gemini` may be selected when the route is eligible. The active profile or documented repo-local visual heuristic may rank Gemini first for image/icon/decorative visual work.
- The Claude-line canonical schema may include the shared `externalModelMode`, `externalGeminiFallbackMode` when the resolved provider is Gemini, and `externalClaudeSecretMode` plus `externalClaudeApiMode` when the resolved provider is Claude; `externalClaudeProfile` remains Codex-line only.
- The team template JSON does not change; routing substitutions happen at execution time.
- `Assigned role` in provenance names the internal role being replaced; it does not narrow the adapter to only one profession.
- Resolve any `external` request in this order: `role eligibility -> provider selection -> CLI availability`.
- Unsupported external requests fail fast. There is no generic external adapter for owner roles such as `$product-manager` or `$lead` on the Claude line.
- An explicit request for `external` on an unsupported owner role changes the disclosure, not the eligibility. The orchestrator must say the route is unsupported and reroute honestly.
- If the external CLI is unavailable, the adapter is disabled and the orchestrator may reroute the work to another eligible path.
- The adapter itself must not silently fall back to an internal specialist.
- Independent external adapters may run in parallel when their scopes are disjoint and provider runtimes support concurrent non-interactive execution.
- Parallel external routing is not capped at one instance per helper or provider. If multiple admitted artifacts or disjoint slices honestly need the same provider, the orchestrator may launch repeated same-provider external helpers concurrently.
- Treat same-lane multi-opinion collection and general external fan-out as different mechanisms: `externalOpinionCounts` governs distinct opinions for one lane, while brigade-style fan-out covers multiple independent lanes or slices.
- If native internal slot limits would otherwise block additional independent eligible lanes, prefer available external adapters instead of silently serializing or dropping them.

## Batch-close consultant check

For lead-managed work, every completed task-batch must satisfy the active lane policy's external consultant requirement before closure.

- The check uses `$consultant` as an advisory-only closure sweep; it does not replace reviewers, QA, or human/CI gates.
- Request the external execution path explicitly for this closure check.
- If the external path is unavailable, disabled, or would downgrade to an internal-only run, do not mark the batch closed; record the miss and escalate to the user instead.
- The memo must end with both:
  - **Continuation prompt:** one ready-to-send second prompt that can be used verbatim to continue the work.
  - The continuation prompt must begin with a direct imperative to continue and name the next concrete action.
- Before closure after that memo, reconcile the requested outcome against remaining open obligations; if admitted-scope work remains, keep the batch open.

## Research admission filter

When `$product-manager` admits a new candidate approach into discovery, the roadmap decision package must include:

- **Coherence statement**: what shared state or contract holds this candidate together as one unit
- **Improvement hypothesis**: which baseline it beats, on which cases, by which metric, through which mechanism
- **Non-redundancy argument**: why this is meaningfully different from prior rejects with similar failure modes
- **Expected win cases**: where the candidate is expected to succeed
- **Expected fail cases**: where it is expected to struggle
- **Evaluation metric mapping**: how the candidate's optimization objective maps to the benchmark objective
- **Shortest falsification experiment**: 2–3 cases, clear PASS/FAIL threshold, minimal tuning
- **Implementation seam**: where this lives in the repo (isolated lane, protected surfaces, minimal seam) — confirmed by `$architect` after admission

`$product-manager` enforces 3 pre-admission gates (coherence, improvement hypothesis, non-redundancy). `$analyst` enforces 4 research-phase gates (regression risk, metric alignment, known limits, bounded falsification). `$architect` confirms the implementation isolation gate after admission.

## Interaction types

Eight interaction types classify how roles communicate.

| Type       | Symbol   | Purpose                                                                |
|------------|----------|------------------------------------------------------------------------|
| `DIRECT`   | `->`     | Direct artifact handoff. Default for `requiresLead: false` chains.     |
| `LEAD_MED` | `->L->`  | Every handoff through lead. Default for `requiresLead: true` chains.   |
| `PARALLEL` | `\|\|`   | Parallel execution; single aggregator point.                           |
| `CLAIMS`   | `=>`     | Traveling artifact via `constraints/claims.md`.                        |
| `RETURN`   | `<=`     | Reviewer returns finding to named specialist (structural gaps only).   |
| `ESCALATE` | `^`      | Bounded escalation with specific metrics and question.                 |
| `ADVISORY` | `~>`     | Consultant advisory only; never a pipeline gate.                       |
| `NONE`     | `.`      | No direct interaction.                                                 |

`PARALLEL`, `CLAIMS`, `RETURN`, `ESCALATE` require lead or main conversation authorization.

## Periodic controls

Periodic controls complement stage gates. Stage gates answer "may this item advance?" Periodic controls answer "what drift or staleness should we catch between transitions?"

| Control | Owner | Trigger | Fail action |
| --- | --- | --- | --- |
| Work-items completeness | `$lead` | Session start | Create missing artifacts or park item |
| Freshness audit | `$lead` | Resume / session start | Update `status.md` or park/archive |
| Artifact completeness | `$knowledge-archivist` | Stage change | Restore artifact or route back upstream |
| Index sync | `$knowledge-archivist` | Resume, archive, completion | Update index |
| Risk-routing audit | `$lead` | Weekly or scope change | Reclassify and add missing lanes |
| Repo consistency | `$knowledge-archivist` | Weekly | Open bounded hygiene follow-up |
| Publication-safety spot check | `$lead` | Weekly or before publication | Redact or move to `/.scratch/` |
| Refactor debt scan | `$architecture-reviewer` | Milestone close | Admit bounded refactor item |
| Closure and archive hygiene | `$knowledge-archivist` | Monthly / milestone close | Archive and update index |
| Governance alignment | `$knowledge-archivist` | Governance change | Propagate to all governance files in same commit |
| Documentation sync | `$knowledge-archivist` | Skill, role, or template added/removed/renamed | Update README, INSTALL, install scripts per root CLAUDE.md checklists |
| Batch-close consultant-check | `$lead` | Every completed lead-managed batch | Satisfy the active lane policy's external consultant requirement or keep the batch open and escalate |

## Non-obvious routing pairs

These pairings are not derivable from classification alone — lead must know them:

| Work type | Design role | Implementation role | QA / Review |
| --- | --- | --- | --- |
| Scientific / data visualization | `$computational-scientist` | `$visualization-engineer` | `$qa-engineer` |
| Geometry / spatial computation | `$computational-scientist` | `$geometry-engineer` | `$qa-engineer` + `$architecture-reviewer` |
| Qt model-view heavy | — | `$model-view-engineer` | `$qa-engineer` + `$ui-test-engineer` (both) |
| Graphics with hard GPU/frame budgets | `$performance-engineer` | `$graphics-engineer` | `$qa-engineer` + `$performance-reviewer` |
| Combined critical (max risk) | stack all relevant constraint roles | implementation specialist | `$qa-engineer` + all triggered reviewers |

## How to instruct reviewers

**Claim-Verify**: pass the claims list from the builder's artifact. Tell the reviewer: *"Verify each claim against the artifact. Also identify any risk surfaces not covered by any claim."*

**Adversarial**: pass the implementation artifact only. Tell the reviewer: *"Do not read the upstream design package. Assume an adversary with full knowledge of the implementation. Find the three highest-probability failure or attack vectors and show the exact mechanism for each."*

## Common alias map

- roadmap owner, PM, or milestone owner = `$product-manager`
- `researcher` = `$analyst`
- product clarification = `$product-analyst`
- `backend-dev` = `$backend-engineer`
- `frontend-dev` = `$frontend-engineer`
- `qa` = `$qa-engineer`
- `mathematical-algorithm-scientist` = `$algorithm-scientist`
- `computational scientist` or `numerical-methods-scientist` = `$computational-scientist`
- `archivist`, `knowledge archivist`, or `repo curator` = `$knowledge-archivist`
- `graphics engineer` or `rendering engineer` = `$graphics-engineer`
- `visualization engineer` = `$visualization-engineer`
- `geometry engineer` = `$geometry-engineer`
- `build engineer` or `toolchain engineer` = `$toolchain-engineer`
- `external worker` = `$external-worker`
- `external reviewer` = `$external-reviewer`

## Cross-domain escalation protocol

When a reviewer finds a significant issue outside their domain (e.g., `security-reviewer` spots a performance regression, or `architecture-reviewer` finds a security concern):

1. **Tag the finding** in the review report: `[CROSS-DOMAIN: <target-domain>]` (e.g., `[CROSS-DOMAIN: performance]`, `[CROSS-DOMAIN: security]`).
2. **Do not evaluate severity** outside the reviewer's expertise — state the observation factually and tag it.
3. **The orchestrator** (main conversation or lead) routes the tagged finding to the appropriate specialist for evaluation.
4. The cross-domain finding does NOT block the current review's gate unless the reviewer cannot complete their own domain assessment without it.

Target-domain mapping: `security` → `$security-engineer` or `$security-reviewer`, `performance` → `$performance-engineer` or `$performance-reviewer`, `architecture` → `$architect` or `$architecture-reviewer`, `accessibility` → `$accessibility-reviewer`, `ux` → `$ux-designer` or `$ux-reviewer`.

## Adjacent-issue protocol

When any role discovers a bug, risk, or improvement opportunity outside the approved change surface:

1. **File it** in `work-items/bugs/` using the bug registry format (from `qa-engineer.md`), with `context: adjacent-finding` and `status: open`.
2. **Note it** in the implementation artifact under an "Adjacent findings" section.
3. **Do NOT expand scope** to fix it. The orchestrator decides priority and scheduling.
4. If the adjacent issue blocks the current phase (e.g., the phase depends on broken adjacent code), return `BLOCKED:prerequisite` instead of working around it.

## Artifact invalidation protocol

When an upstream artifact is revised after downstream artifacts have already been accepted:

1. **Mark downstream artifacts as stale.** In `status.md`, add `stale-since: <timestamp>` to the affected artifact references.
2. **The orchestrator must re-validate** each stale artifact before it is used as input to further stages. Re-validation means either:
   - Confirming the downstream artifact is unaffected by the upstream change (annotate why), or
   - Re-running the downstream stage with the updated upstream artifact.
3. **Scope**: research → design → plan → implementation. A change to research may invalidate design; a change to design may invalidate the plan. Implementation artifacts are invalidated if their plan phase changed.

## REVISE iteration cap

Any REVISE loop (QA, reviewer, or other gate returning REVISE) is capped at **3 iterations** per stage:

1. **Iteration 1-3**: The implementer (or responsible role) addresses findings and re-submits. The gate re-evaluates.
2. **After iteration 3**: If the gate still returns REVISE, escalate to the user with:
   - Summary of all 3 iterations and what was attempted
   - Remaining unresolved findings
   - Recommendation: fix approach, redesign, or defer
3. The user decides: continue fixing, re-plan, or accept with known issues.
4. The iteration count is tracked in `status.md` under the REVISE loop section.

## Parallel execution protocol

Before launching agents in parallel:

1. **Confirm non-overlapping change surfaces.** Each parallel agent must have an explicitly disjoint set of files it may modify. If change surfaces overlap, serialize the agents instead.
2. **Assign an integration owner.** For `requiresLead: true` chains, lead is the integration owner. For `requiresLead: false`, main conversation is.
3. **After all parallel agents complete**, the integration owner:
   - Checks for semantic conflicts (two agents made assumptions that contradict each other)
   - Checks for unintended interactions (e.g., both agents modified a shared import file that wasn't in either change surface)
   - If conflicts exist, resolve before advancing to the next stage
4. **If a parallel agent returns REVISE or BLOCKED**, handle it independently — other parallel agents are not affected unless the finding impacts their change surface.

## Artifact persistence protocol

Every completed chain that produces an accepted artifact MUST persist it before the session ends. The orchestrator (main conversation or lead) owns persistence — do not invoke a separate agent for a single file write.

### Three-tier storage

| Tier | Location | Purpose | Content |
| --- | --- | --- | --- |
| **Canonical** | `work-items/active/<slug>/` | Source of truth for active work | `research.md`, `design.md`, `plan.md`, `review.md`, `report.md`, `status.md`, `brief.md` |
| **Session log** | `.reports/YYYY-MM/` | Brief record of what happened in each session | `report(<role>)-YYYY-MM-DD_HH-MM_topic.md` — summary, not a copy of the canonical artifact |
| **Plan log** | `.plans/YYYY-MM/` | Plan snapshots when a plan is created or materially revised | `plan(<role>)-YYYY-MM-DD_HH-MM_topic.md` |

`<role>` is the `subagent_type` that produced the artifact (e.g., `analyst`, `security-reviewer`, `planner`, `qa-engineer`).

### Where to save

| Artifact type | Canonical (work-items) | Session log (.reports/) |
| --- | --- | --- |
| Research memo | `work-items/active/<slug>/research.md` | Session log entry summarizing findings |
| Design artifact | `work-items/active/<slug>/design.md` | Session log entry if design session was non-trivial |
| Plan | `work-items/active/<slug>/plan.md` | Plan snapshot in `.plans/YYYY-MM/` |
| Review report | `work-items/active/<slug>/review.md` | Session log entry summarizing review outcome |
| Security review | `work-items/active/<slug>/security-review.md` | Session log entry summarizing review outcome |
| Test report | `work-items/active/<slug>/test-report.md` | Session log entry summarizing QA verdict |
| Advisory memo | `work-items/active/<slug>/advisory.md` | Session log entry summarizing advisory |
| Bug finding | `work-items/bugs/YYYY-MM-DD_slug.md` | — |
| Performance issue | `work-items/performance/YYYY-MM-DD_slug.md` | — |

Session logs are summaries pointing to canonical artifacts, not copies. See `AGENTS.md` § "Session logging rule" for the mandatory logging contract.

**Standalone chains** (no active work-item): create a work-item folder if the result is worth preserving, or save to `.reports/` / `.plans/` only as a session log.

### When to save

- **After the final "Report" step** in any skill — the orchestrator saves the artifact before presenting it to the user.
- **After each stage transition** in multi-stage chains — the accepted artifact is saved alongside `status.md` (per recovery rule).
- **After QA/reviewer PASS** — the final verdict is saved to the work-item.

### When NOT to save

- Interactive sessions (`/agents-qa-session`) — the QA agent saves bug files, but the session itself is ephemeral.
- Aborted or BLOCKED chains — save recovery state in `work-items/active/` but not a report.

### Knowledge archivist

Invoke `$knowledge-archivist` only for complex document operations: reorganization, migration, multi-file index sync, archive moves. Not for routine artifact saves.

## Governance sources

- `.claude/CLAUDE.md` is the governance source of truth (auto-loaded into every conversation).
- `lead.md` is the self-contained lead operating guide (loaded when lead is invoked).
- This file is the on-demand reference for routing, controls, and aliases.
