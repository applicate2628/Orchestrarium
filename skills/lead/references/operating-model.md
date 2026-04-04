# Operating Model Notes

Use this reference when the lead needs routing, gate, or governance guidance beyond the core skill.

## Delivery loops

- Roadmap and intake loop:
  `product-manager -> product-analyst -> lead`
- Delivery loop for an approved item:
  `lead -> research -> design -> plan -> implement -> QA/review -> lead`
- Re-intake loop for an in-flight item whose admitted scope, priority, or milestone intent has changed:
  `lead -> product-manager -> lead`

The roadmap loop decides what should enter discovery or delivery. The delivery loop decides how an approved item is executed safely.

## Rolling-loop execution

- The system operates as a rolling loop, not a stop-and-wait chain.
- `PASS` immediately advances to the next approved role.
- `REVISE` stays inside the same role for a bounded correction.
- `BLOCKED` is reserved for real external blockers, missing decisions, or unavailable prerequisites.
- Close specialist sessions once their artifact is accepted, handed off, or explicitly parked. Keep them open only for a bounded `REVISE` or an immediate same-scope follow-up; close `BLOCKED` and advisory-only consultant sessions once routing or advisory handoff is complete.
- A material revision to an accepted upstream artifact invalidates dependent downstream `PASS` states; the lead marks the affected artifacts for re-review before continuing the pipeline.
- Handoff latency should stay low: do not pause between accepted artifacts unless a true gate failure or a policy-required human or CI check requires it.

## Change classification

- Classify the change before selecting routing: `cosmetic`, `additive`, `behavioral`, or `breaking-or-cross-cutting`.
- `cosmetic` usually stays on the normal delivery loop with QA only.
- `additive` stays on the normal delivery loop unless it introduces a new risk owner.
- `behavioral` should add factual/design scrutiny first when evidence is thin, then QA and reviewers as needed for contracts, user flow, or failure modes.
- `breaking-or-cross-cutting` should force stronger routing: architect, planner, re-review of affected downstream artifacts, and integration ownership when multiple phases or specialists must land together.

## Fact-first workflow

- Prefer factual roles before interpretive roles when the next decision depends on missing evidence.
- `product-analyst` and `analyst` establish the factual base; `product-manager`, `architect`, and specialist design lanes interpret that base and make bounded decisions.
- Every decision artifact should separate confirmed facts, explicit assumptions, judgment calls, and unresolved questions.
- Do not substitute brainstorming for discovery when the missing input can be gathered as evidence.
- Use `$consultant` only as optional independent judgment after the best available factual slice has already been assembled.

## Canonical routing patterns

- Roadmap prioritization or milestone shaping:
  `product-manager -> lead`
- Roadmap item that needs factual product clarification before admission:
  `product-manager -> product-analyst -> lead`
- Advisory-only independent consultation:
  `lead -> consultant`
- In-flight item whose admitted scope, priority, or milestone intent has drifted:
  `lead -> product-manager -> lead`
- Basic CRUD or integration work:
  `lead -> analyst -> architect -> planner -> implementation -> qa-engineer -> lead`
- Product-sensitive work with unclear scope or user impact:
  `lead -> product-analyst -> analyst -> architect -> planner -> implementation -> qa-engineer -> lead`
- UX-sensitive user-facing work with meaningful interaction design:
  `lead -> product-analyst -> analyst -> architect -> ux-designer -> planner -> frontend-engineer (web/React) / qt-ui-engineer (Qt desktop) -> qa-engineer -> ux-reviewer -> lead`
- Algorithmically sensitive work:
  `lead -> analyst -> architect -> algorithm-scientist -> planner -> implementation -> qa-engineer -> lead`
- Scientific-modeling or numerical-method work:
  `lead -> analyst -> architect -> computational-scientist -> planner -> implementation -> qa-engineer -> lead`
- Repository hygiene, documentation, or archival-consistency work:
  `lead -> knowledge-archivist -> lead`
- Performance-sensitive work:
  `lead -> analyst -> architect -> performance-engineer -> planner -> implementation -> qa-engineer -> lead`
- Reliability-sensitive work:
  `lead -> analyst -> architect -> reliability-engineer -> planner -> implementation -> qa-engineer -> lead`
- Performance-critical work with hard budgets or public SLA:
  `lead -> analyst -> architect -> performance-engineer -> planner -> implementation -> qa-engineer -> performance-reviewer -> lead`
- Security-sensitive work:
  `lead -> analyst -> architect -> security-engineer -> planner -> implementation -> qa-engineer -> security-reviewer -> lead`
- Platform-heavy work:
  `lead -> analyst -> architect -> reliability-engineer -> planner -> platform-engineer -> qa-engineer -> lead`
- Build-system or toolchain work:
  `lead -> analyst -> planner -> toolchain-engineer -> qa-engineer -> lead`
- Graphics or rendering work:
  `lead -> analyst -> architect -> planner -> graphics-engineer -> qa-engineer -> lead`
- Graphics work with hard frame, memory, or GPU budgets:
  `lead -> analyst -> architect -> performance-engineer -> planner -> graphics-engineer -> qa-engineer -> performance-reviewer -> lead`
- Scientific or data-visualization work:
  `lead -> analyst -> architect -> computational-scientist -> planner -> visualization-engineer -> qa-engineer -> lead`
- Geometry or spatial-computation work:
  `lead -> analyst -> architect -> computational-scientist -> planner -> geometry-engineer -> qa-engineer -> architecture-reviewer -> lead`
- Qt desktop UI work:
  `lead -> analyst -> architect -> planner -> qt-ui-engineer -> ui-test-engineer -> lead`
- Qt model-view-heavy work:
  `lead -> analyst -> architect -> planner -> model-view-engineer -> ui-test-engineer -> lead`
- High-governance or architecture-sensitive work:
  `lead -> analyst -> architect -> planner -> implementation -> qa-engineer -> architecture-reviewer -> lead`
- Extensibility-sensitive or low-blast-radius work:
  `lead -> analyst -> architect -> planner -> implementation -> qa-engineer -> architecture-reviewer -> lead`
- UX-sensitive user-facing work without a separate UX design lane:
  `lead -> analyst -> architect -> planner -> frontend-engineer (web/React) -> qa-engineer -> ux-reviewer -> lead`
- Accessibility-sensitive user-facing work:
  `lead -> analyst -> architect -> planner -> qt-ui-engineer (Qt desktop) -> ui-test-engineer -> accessibility-reviewer -> lead`
- Combined critical work:
  `lead -> product-analyst -> analyst -> architect -> algorithm-scientist -> security-engineer -> performance-engineer -> reliability-engineer -> planner -> implementation -> qa-engineer -> architecture-reviewer -> performance-reviewer -> security-reviewer -> lead`

## Stage gates

- After `product-manager`: priority, sequencing rationale, bounded initiative scope, and admission decision are explicit.
- After `product-analyst`: product context, scope evidence, metrics, and open product questions are explicit.

- After `analyst`: relevant system areas, contracts, constraints, and unknowns are explicit.
- After `architect`: chosen design, rejected alternatives, boundaries, approved extension seams, dependency direction, stable contracts, expected blast radius, failure modes, and test strategy are explicit.
- After `ux-designer`: scoped user flows, interaction states, content hierarchy, usability constraints, and UX acceptance guidance are explicit.
- After `algorithm-scientist`: correctness, complexity, invariants, and algorithmic failure modes are explicit.
- After `computational-scientist`: the scientific model, assumptions, units, discretization or solver strategy, validation criteria, and numerical failure modes are explicit.
- After `security-engineer`: threat model, trust boundaries, required controls, and must-fix constraints are explicit.
- After `performance-engineer`: budgets, methodology, bottlenecks, and blocking performance risks are explicit.
- After `reliability-engineer`: SLOs, failure modes, degradation behavior, observability expectations, and recovery requirements are explicit.
- After `knowledge-archivist`: canonical docs, plans, reports, references, archive locations, and repository-facing links are consistent or explicitly blocked.
- After `planner`: phases, dependencies, file scope, allowed change surface, must-not-break surfaces, checks, and rollback notes are explicit.
- After `planner`: shared or core module changes, if any, are isolated into explicit enabling phases instead of being hidden inside local feature work.
- After implementation: the phase stayed within scope, includes required tests, and reports changed files and risks.
- Before QA for a multi-phase or multi-specialist change: one explicit integration owner, one integrated artifact, and cross-phase compatibility checks are explicit.
- After `toolchain-engineer`: build graph behavior, packaging, reproducibility expectations, and local or CI parity are validated or explicitly blocked.
- After `qa-engineer`: acceptance criteria, regressions, edge cases, and basic performance acceptance are verified or explicitly blocked.
- After `ui-test-engineer`: Qt UI interaction states, focus behavior, visual regressions, and high-DPI or theme-sensitive regressions are verified or explicitly blocked.
- After `architecture-reviewer`: the implementation still fits the accepted design, preserves cohesion and dependency direction, uses approved seams, and keeps blast radius within the agreed change surface.
- After `performance-reviewer`: performance evidence and methodology are valid and there are no blocking regressions.
- After `security-reviewer`: no blocking security risks remain and must-fix items are closed.
- After `ux-reviewer`: there are no blocking usability, accessibility, or flow-quality issues.
- After `accessibility-reviewer`: there are no blocking keyboard, focus, labeling, contrast, or assistive-technology issues for the scoped surface.
- After the human or CI gate: required approvals and automated checks are complete.

## Repository task memory

- Use `work-items/index.md` as the recovery entry point for this repository.
- Keep each active lead-routed non-trivial item in `work-items/active/<date>-<slug>/`.
- Require `roadmap.md`, `brief.md`, and `status.md` before non-trivial work starts or resumes.
- Require `plan.md` before implementation or review begins.
- If the current stage depends on upstream artifacts such as research, design, specialist constraints, phase plan, or required review reports, those artifacts must exist and be current before work continues.
- Update `status.md` after accepted artifacts, interruptions, or stage changes so work can resume without relying on chat memory.
- If the required task-memory artifacts are missing or stale, stop and restore them before continuing delivery.
- Use `notes.md` or `notes/` for technical notes and discoveries; keep accepted long-lived decisions in the design or ADR artifact.

## Lead quick checklist

Do:

- assign one explicit owner for each critical risk
- give each role only the minimal approved context it needs
- require one artifact and one explicit gate decision per stage
- block progression until the current artifact is accepted
- keep one source of truth for the brief, accepted decisions, constraints, and status
- keep durable task memory in `work-items/` instead of relying on session memory
- route roadmap questions to `product-manager` instead of burying them inside the lead lane
- route an in-flight item back to `product-manager` when admitted scope, priority, or milestone intent changes materially
- route unknowns to factual roles before escalating into opinion-heavy discussion
- assign one explicit integration owner before QA when multiple implementation phases or specialists must land together

Do not:

- assign one subagent to do the whole feature
- let delivery start before the roadmap or intake decision is explicit when prioritization is still open
- let delivery silently redefine an admitted item when the work really needs re-intake
- mix research, design, planning, implementation, and acceptance without a strong reason
- skip gates for speed
- let taste or unsupported opinion replace evidence when the workflow can still gather facts
- expect QA to replace specialist design lanes
- allow scope drift or broad write access by default
- hand QA a partially integrated multi-phase change without an explicitly named integration owner

## Review strategy selection

The lead chooses the review strategy for each risk domain when invoking an independent reviewer. Two strategies are available. Use the decision table below.

### Strategy A — Claim-Verify

The upstream specialist (builder) includes an explicit **claims section** in their artifact: a numbered list of falsifiable guarantees this artifact makes.

The reviewer receives:
- the implementation artifact
- the claims list only — **not** the full design package or reasoning chain of the builder

The reviewer's job:
1. Verify each claim against the artifact or implementation.
2. Find risk surfaces or threat classes not covered by any claim.

Use Claim-Verify when:
- The risk is well-understood and the builder can enumerate what they are guaranteeing
- The goal is catching execution errors (implementation does not satisfy stated design)
- Speed matters — claim-verify is faster than adversarial review
- Example domains: security controls on a known threat model, performance against defined budgets, architecture against accepted design

### Strategy B — Adversarial Review

The reviewer receives the implementation artifact only. They do **not** receive the builder's design package or reasoning.

The reviewer's explicit mandate: assume an adversary or failure mode not anticipated by the builder. Find the three highest-probability ways this artifact fails, breaks, or is exploited. For each, show the exact mechanism.

Use Adversarial Review when:
- The risk surface is novel, poorly understood, or the builder may have systematic blind spots
- The goal is finding design-level gaps the builder never modeled
- Cost of missing an unknown risk is high
- Example domains: security on new trust boundaries or external integrations, architecture on new shared abstractions, numerical stability on novel algorithms

### Decision table

| Signal | Claim-Verify | Adversarial |
|---|---|---|
| Risk surface is known and bounded | preferred | optional |
| Risk surface is novel or externally exposed | optional | preferred |
| Builder has strong domain expertise | preferred | optional |
| Builder is working in unfamiliar territory | optional | preferred |
| Speed is a constraint | preferred | — |
| Consequence of a missed unknown is critical | optional | preferred |

### How to instruct the reviewer

**Claim-Verify:** Pass the claims list from the builder's artifact explicitly. Tell the reviewer: "Verify each claim. Also identify any risk surfaces not covered by any claim."

**Adversarial:** Pass the implementation artifact only. Tell the reviewer: "Do not read the upstream design package. Assume an adversary with full knowledge of the implementation. Find the three highest-probability failure or attack vectors and show the exact mechanism for each."

### Combining both

For critical changes, run both in sequence: Claim-Verify first (fast, catches execution errors), then Adversarial (slower, catches design-level blind spots). The Adversarial reviewer still does not receive the Claim-Verify report — independence must be preserved.

---

## Builder and blocker separation

- `product-manager` owns roadmap priority, sequencing, and admission decisions.
- `product-analyst` and `analyst` gather facts.
- `architect`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` define constraints and recommendations.
- `ux-designer` defines scoped user-facing interaction design before planning and implementation when UX ownership is needed.
- `knowledge-archivist`, `backend-engineer`, `frontend-engineer`, `graphics-engineer`, `visualization-engineer`, `geometry-engineer`, `qt-ui-engineer`, `model-view-engineer`, `data-engineer`, `toolchain-engineer`, and `platform-engineer` implement approved phases.
- `qa-engineer` and `ui-test-engineer` verify correctness and regressions in their scope.
- `architecture-reviewer`, `performance-reviewer`, `security-reviewer`, `ux-reviewer`, and `accessibility-reviewer` act as independent blockers when their risk domain matters.
- `consultant` is advisory-only and not part of the blocker chain; if an external provider is unavailable, the lead may fulfill this role through an independent internal subagent instead.
- The role map in this reference describes the canonical core team only. If a narrower installed specialist outside the core team is a better fit for the scoped work, the lead may use it; if the current repo/workspace defines or clearly implies a repo-local specialist, the lead may use that specialist. Using such a specialist does not add it to the canonical map automatically.

Do not let a role that defines a critical constraint act as the only approval gate for that same risk.

## Interaction topology

- Default topology is hub-and-spoke through `$lead` for delivery work.
- Default topology is hub-and-spoke through `$product-manager` for roadmap and intake work.
- If delivery discovers that the admitted item itself has changed materially, `$lead` routes it back to `$product-manager` for re-intake instead of renegotiating scope privately inside the delivery lane.
- Subagents hand off artifacts, not direct task assignments, to one another.
- Factual clarification should move upstream through the orchestrating owner before interpretive roles continue.
- A downstream role may consume an accepted upstream artifact, but it should not silently rewrite that artifact.
- If a role finds a conflict with an upstream artifact, it returns `REVISE` or `BLOCKED` to the orchestrating owner instead of negotiating scope privately.
- Independent reviewers return findings to the orchestrating owner; they do not directly re-task implementation roles.
- Direct role-to-role collaboration is allowed only when the orchestrating owner explicitly approves the pair, scope, and expected artifact boundary.

## Governance sources

- [references/subagent-operating-model.md](../../../references/subagent-operating-model.md) is the repository-wide operating-model source of truth.
- [references/repository-task-memory.md](../../../references/repository-task-memory.md) is the repository-wide task-memory source of truth.
- This file is the condensed lead-facing operating guide and should stay aligned with, not diverge from, the repository-wide model.
- [AGENTS.md](../../../AGENTS.md) is the repo entrypoint and role index.

## Re-intake and integration ownership

- Re-intake is not the same as `REVISE`. Use re-intake when the admitted item itself has changed; use `REVISE` when the current role can still correct its artifact without changing the admitted item.
- If scope drift, priority changes, or milestone reshaping materially redefine the work, `$lead` stops delivery progression and routes the item back to `$product-manager`.
- If a change spans multiple implementation phases or specialists, `$lead` assigns one explicit integration owner before QA.
- The integration owner assembles one coherent integrated artifact, checks cross-phase compatibility, and hands one verification-ready result to QA or the relevant reviewers.

## Parallelism guidance

- Parallelize read-heavy work such as research, triage, and test analysis when scopes are independent.
- Parallelize write-heavy work only after contracts and phase boundaries are frozen.
- Do not run two writing roles in the same area without explicit ownership boundaries.

## Change-isolation guidance

- Prefer additive change through existing or explicitly approved seams over cross-cutting edits.
- Treat a local feature that requires unrelated module changes as a design or planning problem until proven otherwise.
- Require explicit justification before introducing new shared abstractions or broadening dependency direction.
- Name nearby but nominally unrelated surfaces that need smoke coverage when their contracts are close to the change surface.

## Governance artifacts to keep near the code

- roadmap decision package
- canonical brief
- status log
- product brief, if used
- research memo
- design doc or ADR
- UX design package, if used
- algorithm note, if used
- computational model package, if used
- security design package, if used
- performance package, if used
- reliability design package, if used
- phase plan
- technical notes, if needed
- repository stewardship package, if used
- toolchain implementation package, if used
- QA verification report
- Qt UI verification report, if used
- architecture review report, if used
- performance review report, if used
- security review report, if used
- UX review report, if used
- accessibility review report, if used
- advisory memo, if a consultant was invoked

## Common alias map

- roadmap owner, PM, or milestone owner means `$product-manager`
- `researcher` means `$analyst`
- product clarification means `$product-analyst`
- `backend-dev` means `$backend-engineer`
- `frontend-dev` means `$frontend-engineer`
- `qa` means `$qa-engineer`
- `mathematical-algorithm-scientist` means `$algorithm-scientist`
- `computational scientist` or `numerical-methods-scientist` means `$computational-scientist`
- `archivist`, `knowledge archivist`, or `repo curator` means `$knowledge-archivist`
- `graphics engineer` or `rendering engineer` means `$graphics-engineer`
- `visualization engineer` means `$visualization-engineer`
- `geometry engineer` means `$geometry-engineer`
- `build engineer` or `toolchain engineer` means `$toolchain-engineer`

