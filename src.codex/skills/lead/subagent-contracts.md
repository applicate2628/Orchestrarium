# Subagent Contracts

Use these templates when the lead needs a crisp handoff or a gate checklist.

## Shared handoff template

```text
Role:
Goal:
Approved inputs:
- <accepted artifact or fact>
- <accepted artifact or fact>
Allowed tools:
- <allowed tool>
- <allowed tool>
Scope:
- <allowed area>
Out of scope:
- <forbidden area>
Allowed change surface:
- <approved files, modules, or seams>
Must-not-break surfaces:
- <nearby but unrelated areas that need isolation or smoke coverage>
Constraints:
- <constraint>
- <constraint>
Expected artifact:
- <one artifact>
Acceptance criteria:
- <criterion 1>
- <criterion 2>
Gate to next stage:
- <what must be proven>
```

## Artifact gate — no delegation without brief

A lead MUST NOT delegate work until the work-item folder contains a verified `brief.md` and `status.md`.

- `brief.md` must have explicit scope, out-of-scope, acceptance criteria, required roles, and critical risks with owners.
- `status.md` must have a current snapshot with stage, last accepted artifact, and next concrete action.
- If either artifact is missing, stale, or incomplete, the lead restores them BEFORE delegating any specialist role.
- This gate is non-negotiable for non-trivial work. The only exception is the additive fast lane where the lead records the decision in status.md instead.

### status.md format

```markdown
---
template: <template name>
orchestrator: main | lead
started: <YYYY-MM-DD>
updated: <YYYY-MM-DD HH:MM>
---

## Current state
- **Stage**: <current pipeline stage>
- **Orchestrator role**: <main conversation | $lead>
- **Last accepted artifact**: <artifact name and date>

## Active agents
| Agent | Role | Status | Launched |
|---|---|---|---|
| ... | ... | running / waiting | YYYY-MM-DD |

## Completed agents
| Agent | Role | Result | Artifact |
|---|---|---|---|
| ... | ... | PASS / REVISE / BLOCKED | <artifact path> |

## REVISE loop (include only when active)
| Field | Value |
|---|---|
| Role | <role under revision> |
| Iteration | <1-3> |
| Remaining findings | <count> |
| Escalation threshold | 3 |

## Next action
<What happens next — specific role, artifact, and gate expected>
```

## Shared response format

```text
1. Summary
2. Artifact
3. Risks / Unknowns
4. Recommended next role
5. Gate: PASS | REVISE | BLOCKED:<class> | RETURN(role)
```

### BLOCKED classification

| Class | Meaning | Orchestrator action |
|---|---|---|
| `BLOCKED:dependency` | Cannot proceed — missing tool, environment, access, or information that no current agent can provide | Present to user for resolution |
| `BLOCKED:prerequisite` | Discovered adjacent work that must complete first (e.g., broken adjacent module, missing migration) | File in `work-items/bugs/` → user decides priority → resume when resolved |

If no class is specified, treat as `BLOCKED:dependency` (conservative default).

Fact-first note:
- When a role makes a decision or recommendation, it should clearly distinguish confirmed facts, assumptions, and judgment.
- If the main gap is missing evidence, recommend the appropriate factual role instead of escalating straight into broader opinion.

Consultant exception:
- `$consultant` returns the same first four sections, but ends with `5. Advisory status: NON-BLOCKING`.
- If the external provider is unavailable or fails, the lead may use an independent internal subagent as `$consultant` with the same advisory-only contract and the same response format.

## Role map

Use these current skill names in this repository:

- Treat this role map as the canonical core team only, not as an exhaustive inventory of every installed or repo-local specialist.
- If a narrower installed specialist outside the core team is a better fit for scoped work, the lead may use it.
- If the current repo or workspace defines or clearly implies a repo-local specialist, the lead may use that specialist without adding it to the canonical team map.

- roadmap ownership, milestone shaping, or prioritization maps to `$product-manager`
- `researcher` maps to `$analyst`
- product or business research maps to `$product-analyst`
- UX design for user flows, interaction states, or content hierarchy maps to `$ux-designer`
- `backend-dev` maps to `$backend-engineer`
- `frontend-dev` maps to `$frontend-engineer`
- `qa` maps to `$qa-engineer`
- `mathematical-algorithm-scientist` maps to `$algorithm-scientist`
- scientific modeling or numerical methods maps to `$computational-scientist`
- repository hygiene, documentation curation, or archival consistency maps to `$knowledge-archivist`
- graphics or rendering implementation maps to `$graphics-engineer`
- scientific or data visualization implementation maps to `$visualization-engineer`
- geometry or spatial computation implementation maps to `$geometry-engineer`
- Qt desktop UI implementation maps to `$qt-ui-engineer`
- Qt model or view implementation maps to `$model-view-engineer`
- build systems, packaging, or toolchain implementation maps to `$toolchain-engineer`

## Product Manager

Use when the task is about roadmap ownership, initiative prioritization, milestone shaping, or admission into discovery or delivery.

Return exactly:
- one roadmap decision package

Acceptance criteria:
- the priority decision, sequencing rationale, and bounded scope are explicit
- the package is ready for `$lead`, `$product-analyst`, or `$analyst`
- no architecture, implementation plan, or delivery ownership is embedded in the roadmap decision

## Analyst

Use for fact-finding only.

Return exactly:
- one factual research memo

Acceptance criteria:
- every claim is tied to source evidence or direct code inspection
- assumptions and unknowns are explicit
- no recommendations are included

## Product Analyst

Use for factual product clarification before design.

Return exactly:
- one product brief

Acceptance criteria:
- scope, constraints, and open questions are evidence-backed
- the artifact stays upstream of design and delivery
- no solution decision is embedded in the brief

## Architect

Use after research is accepted.

Return exactly:
- one design package

Acceptance criteria:
- the chosen design is traceable to accepted facts and constraints
- approved extension seams, stable contracts, dependency direction, and expected blast radius are explicit
- alternatives, interfaces, failure modes, and test strategy are explicit
- no implementation code is included

## Algorithm Scientist

Use when the problem needs formal mathematical or algorithmic framing before implementation.

Return exactly:
- one algorithm note

Acceptance criteria:
- the problem statement, invariants, objectives, and assumptions are precise
- complexity, stability, or probabilistic tradeoffs are explicit
- no implementation code is included

## Computational Scientist

Use when the problem needs scientific modeling, simulation, or numerical-method framing before implementation.

Return exactly:
- one computational model package

Acceptance criteria:
- the model, assumptions, units, and state definitions are precise
- discretization, solver strategy, validation criteria, and numerical risks are explicit
- no implementation code is included

## Security Engineer

Use when the solution needs secure design constraints before planning or implementation.

Return exactly:
- one security design package

Acceptance criteria:
- threat model, trust boundaries, and required controls are explicit
- must-fix constraints are clear
- the result is ready for planning and later `security-reviewer`

## Performance Engineer

Use when the solution needs explicit performance constraints or bottleneck modeling before planning or implementation.

Return exactly:
- one performance package

Acceptance criteria:
- success metrics, budgets, and methodology are explicit
- expected or observed bottlenecks are documented
- the result is ready for planning and later `performance-reviewer`

## Reliability Engineer

Use when the solution needs explicit operability and failure-mode constraints before planning or implementation.

Return exactly:
- one reliability design package

Acceptance criteria:
- SLOs, failure modes, degradation behavior, and recovery expectations are explicit
- observability and rollout or rollback constraints are concrete
- the result is ready for planning and later implementation or review

## UX Designer

Use when approved user-facing work needs interaction design before planning and implementation.

Return exactly:
- one UX design package

Acceptance criteria:
- scoped surfaces, user flows, interaction states, and content hierarchy are explicit
- empty, loading, error, and success behavior is defined for each relevant screen or component
- usability constraints and accessibility expectations are called out
- the result is ready for planner and implementation roles without requiring them to redesign in code
- no roadmap reprioritization, architecture redesign, or implementation code is included

## Planner

Use after the required design and specialist constraints are accepted.

Return exactly:
- one delivery plan

Acceptance criteria:
- phases are small and independently checkable
- allowed change surface, must-not-break surfaces, dependencies, checks, and rollback notes are explicit
- shared or core module changes are isolated and justified explicitly
- code is not written in the plan artifact

## Knowledge Archivist

Use when the approved phase is primarily repository hygiene, documentation curation, report or plan maintenance, reference upkeep, or archival consistency.

Return exactly:
- one repository stewardship package

Acceptance criteria:
- the change stays within approved repository knowledge scope
- canonical docs, plans, reports, references, and archive locations are updated consistently
- path, link, or cross-reference checks were run or clearly reported as blocked

## Implementation Specialists

Use only after plan approval.

Return exactly:
- one implementation package

Acceptance criteria:
- changes stay inside approved scope
- changes stay inside the approved change surface or explicitly escalate a conflict
- required tests and checks were run or explicitly blocked
- design or plan conflicts are escalated instead of patched over

## Toolchain Engineer

Use when the approved phase is primarily build-system, packaging, compiler, linker, preset, or reproducible-toolchain work.

Return exactly:
- one toolchain implementation package

Acceptance criteria:
- the change stays within approved toolchain scope
- build graph behavior, packaging, reproducibility, and local or CI parity remain aligned with the accepted plan
- planned build and packaging checks were run or clearly reported as blocked

## Platform Engineer

Use when the approved phase is primarily infrastructure, CI or CD, deployment, runtime platform, or developer-tooling work.

Return exactly:
- one platform implementation package

Acceptance criteria:
- the change stays within approved platform scope
- rollout or rollback notes are explicit
- platform validations were run or clearly reported as blocked

## Graphics Engineer

Use when the approved phase is primarily 2D or 3D rendering work such as render paths, shaders, materials, scene updates, asset flow, or frame behavior.

Return exactly:
- one graphics implementation package

Acceptance criteria:
- the change stays within approved graphics scope
- render-path behavior, resource lifecycle, and scene assumptions remain aligned with the accepted plan
- planned checks and relevant performance evidence were run or clearly reported as blocked

## Visualization Engineer

Use when the approved phase is primarily scientific or data visualization work such as charts, overlays, views, scales, legends, coordinate transforms, or exploration interactions.

Return exactly:
- one visualization implementation package

Acceptance criteria:
- the change stays within approved visualization scope
- visual encodings, transforms, units, and interactions remain aligned with the accepted plan
- planned checks were run or clearly reported as blocked

## Geometry Engineer

Use when the approved phase is primarily geometry or spatial-computation work such as transforms, predicates, intersections, meshing, tessellation, or spatial indexing.

Return exactly:
- one geometry implementation package

Acceptance criteria:
- the change stays within approved geometry scope
- coordinate conventions, tolerances, degeneracy handling, and edge-case behavior remain aligned with the accepted plan
- planned checks and tests were run or clearly reported as blocked

## Qt UI Engineer

Use when the approved phase is primarily Qt desktop UI work on windows, dialogs, widgets, focus, keyboard behavior, or approved theme and high-DPI handling.

Return exactly:
- one Qt UI implementation package

Acceptance criteria:
- the change stays within approved Qt UI scope
- interaction behavior, focus, and widget lifecycle remain aligned with the accepted plan
- planned checks were run or clearly reported as blocked

## Model-View Engineer

Use when the approved phase is primarily Qt model or view work such as models, proxies, delegates, selection, or large tree and table behavior.

Return exactly:
- one model or view implementation package

Acceptance criteria:
- the change stays within approved model or view scope
- index semantics, selection, sorting or filtering, and persistence behavior remain correct
- planned checks and tests were run or clearly reported as blocked

## QA Engineer

Use after implementation.

Return exactly:
- one verification report

Acceptance criteria:
- acceptance criteria are mapped to evidence
- regressions and edge cases are addressed
- nearby must-not-break surfaces from the plan are smoke-checked or explicitly blocked
- basic performance acceptance is included or explicitly blocked

## UI Test Engineer

Use when Qt desktop UI regressions need dedicated verification beyond the generic QA lane.

Return exactly:
- one Qt UI verification report

Acceptance criteria:
- interaction states, keyboard and focus behavior, and visual regressions are checked for the scoped surface
- visual evidence is included when appearance or layout changed
- blocking UI regressions are explicit and reproducible

## Independent Reviewers

Use after QA or when an explicit review gate is required.

Return exactly:
- one review report

Acceptance criteria:
- checks align with the accepted design, plan, and specialist constraints
- findings are concrete and reproducible
- approval is explicit, not implied

## Architecture Reviewer

Use when maintainability, extensibility, low coupling, or blast-radius control need an independent gate before merge or release.

Return exactly:
- one architecture and quality review report

Acceptance criteria:
- cohesion, coupling, extension-seam use, and dependency direction are checked against the accepted design
- hidden cross-cutting edits and unrelated-module churn are called out explicitly
- approval or rejection is explicit

## UX Reviewer

Use when user-facing quality needs an independent gate before merge or release.

Return exactly:
- one UX review report

Acceptance criteria:
- usability, accessibility, and flow issues are scoped and evidence-based
- blocking issues are clearly separated from optional polish
- approval or rejection is explicit

## Accessibility Reviewer

Use when keyboard access, focus order, labeling, contrast, or assistive-technology exposure need an independent gate before merge or release.

Return exactly:
- one accessibility review report

Acceptance criteria:
- accessibility findings are scoped and evidence-based
- blocking accessibility issues are separated from non-blocking improvements
- approval or rejection is explicit

## Consultant

Use only when the lead wants a non-binding second opinion.

Return exactly:
- one advisory memo

Acceptance criteria:
- the memo is concise, explicit about assumptions, and advisory-only
- it does not route work or pretend to be a gate
- if it finds a real blocker, it points back to the proper specialist role

Invocation note:
- `$consultant` usage rules, toggle check, execution paths, and fallback behavior are in `$CODEX_HOME/skills/consultant/SKILL.md`
- if the external provider fails or is unavailable, fall back to an independent internal subagent consultant with the same advisory-only contract

## Interaction rules

- The orchestrating owner controls routing:
  - `$product-manager` for roadmap and intake
  - `$lead` for approved delivery work
- Subagents communicate by producing accepted artifacts for the next role, not by assigning work directly to peers.
- If a role is blocked by missing evidence, it should route back to the orchestrating owner for factual clarification instead of compensating with unsupported opinion.
- A role may request clarification, but it should route the request through the orchestrating owner unless a direct collaboration edge was explicitly approved.
- Reviewers report findings and gate outcomes; they do not directly manage implementation.
- When an upstream artifact is insufficient, return `REVISE` or `BLOCKED` instead of silently redefining the stage contract.

## Gate questions

Ask these before advancing:

1. Is the artifact complete for its stage?
2. Is anything still assumed but unstated?
3. Did the stage stay within its role boundaries?
4. Are the allowed change surface and must-not-break surfaces explicit enough?
5. Is the next stage receiving only the context it truly needs?
6. Is an independent reviewer or human gate still required?
7. Is the blast radius still inside the approved change surface?
