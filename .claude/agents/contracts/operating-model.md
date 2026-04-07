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
4. **Re-intake**: if the admitted item itself changed materially, route back to `product-manager`. Cap: 2 re-intakes, then escalate to user.

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

## Cross-domain escalation protocol

When a reviewer finds a significant issue outside their domain (e.g., `security-reviewer` spots a performance regression, or `architecture-reviewer` finds a security concern):

1. **Tag the finding** in the review report: `[CROSS-DOMAIN: <target-domain>]` (e.g., `[CROSS-DOMAIN: performance]`, `[CROSS-DOMAIN: security]`).
2. **Do not evaluate severity** outside the reviewer's expertise — state the observation factually and tag it.
3. **The orchestrator** (main conversation or lead) routes the tagged finding to the appropriate specialist for evaluation.
4. The cross-domain finding does NOT block the current review's gate unless the reviewer cannot complete their own domain assessment without it.

Target-domain mapping: `security` → `$security-engineer` or `$security-reviewer`, `performance` → `$performance-engineer` or `$performance-reviewer`, `architecture` → `$architect` or `$architecture-reviewer`, `accessibility` → `$accessibility-reviewer`, `ux` → `$ux-designer` or `$ux-reviewer`.

## Adjacent-issue protocol

When an implementer discovers a bug, risk, or improvement opportunity outside the approved change surface:

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
| **Canonical** | `work-items/active/<slug>/` | Clean documentation for active work | `research.md`, `design.md`, `plan.md`, `review.md`, `report.md`, `status.md`, `brief.md` |
| **Session log** | `.reports/YYYY-MM/` | What happened in each session | `report(<role>)-YYYY-MM-DD_HH-MM_topic.md` — intermediate results, session summaries |
| **Plan log** | `.plans/YYYY-MM/` | Plan drafts and iterations | `plan(<role>)-YYYY-MM-DD_HH-MM_topic.md` — plan snapshots |

`<role>` is the `subagent_type` that produced the artifact (e.g., `analyst`, `security-reviewer`, `planner`, `qa-engineer`).

### Where to save

| Artifact type | Canonical (work-items) | Session log |
| --- | --- | --- |
| Research memo | `work-items/active/<slug>/research.md` | `.reports/` copy for traceability |
| Design artifact | `work-items/active/<slug>/design.md` | — |
| Plan | `work-items/active/<slug>/plan.md` | `.plans/` copy for traceability |
| Review report | `work-items/active/<slug>/review.md` | `.reports/` copy |
| Security review | `work-items/active/<slug>/security-review.md` | `.reports/` copy |
| Test report | `work-items/active/<slug>/test-report.md` | `.reports/` copy |
| Advisory memo | `work-items/active/<slug>/advisory.md` | `.reports/` copy |
| Bug finding | `work-items/bugs/YYYY-MM-DD_slug.md` | — |
| Performance issue | `work-items/performance/YYYY-MM-DD_slug.md` | — |

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
