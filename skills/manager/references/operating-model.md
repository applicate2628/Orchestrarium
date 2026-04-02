# Operating Model Notes

Use this reference when the manager needs routing, gate, or governance guidance beyond the core skill.

## Canonical routing patterns

- Advisory-only external consultation:
  `manager -> consultant`
- Basic CRUD or integration work:
  `manager -> analyst -> architect -> planner -> implementation -> qa-engineer -> manager`
- Product-sensitive work with unclear scope or user impact:
  `manager -> product-analyst -> analyst -> architect -> planner -> implementation -> qa-engineer -> manager`
- Algorithmically sensitive work:
  `manager -> analyst -> architect -> algorithm-scientist -> planner -> implementation -> qa-engineer -> manager`
- Scientific-modeling or numerical-method work:
  `manager -> analyst -> architect -> computational-scientist -> planner -> implementation -> qa-engineer -> manager`
- Repository hygiene, documentation, or archival-consistency work:
  `manager -> knowledge-archivist -> manager`
- Performance-sensitive work:
  `manager -> analyst -> architect -> performance-engineer -> planner -> implementation -> qa-engineer -> manager`
- Reliability-sensitive work:
  `manager -> analyst -> architect -> reliability-engineer -> planner -> implementation -> qa-engineer -> manager`
- Performance-critical work with hard budgets or public SLA:
  `manager -> analyst -> architect -> performance-engineer -> planner -> implementation -> qa-engineer -> performance-reviewer -> manager`
- Security-sensitive work:
  `manager -> analyst -> architect -> security-engineer -> planner -> implementation -> qa-engineer -> security-reviewer -> manager`
- Platform-heavy work:
  `manager -> analyst -> architect -> reliability-engineer -> planner -> platform-engineer -> qa-engineer -> manager`
- Build-system or toolchain work:
  `manager -> analyst -> planner -> toolchain-engineer -> qa-engineer -> manager`
- Graphics or rendering work:
  `manager -> analyst -> architect -> planner -> graphics-engineer -> qa-engineer -> manager`
- Graphics work with hard frame, memory, or GPU budgets:
  `manager -> analyst -> architect -> performance-engineer -> planner -> graphics-engineer -> qa-engineer -> performance-reviewer -> manager`
- Scientific or data-visualization work:
  `manager -> analyst -> architect -> computational-scientist -> planner -> visualization-engineer -> qa-engineer -> manager`
- Geometry or spatial-computation work:
  `manager -> analyst -> architect -> computational-scientist -> planner -> geometry-engineer -> qa-engineer -> architecture-reviewer -> manager`
- Qt desktop UI work:
  `manager -> analyst -> architect -> planner -> qt-ui-engineer -> ui-test-engineer -> manager`
- Qt model-view-heavy work:
  `manager -> analyst -> architect -> planner -> model-view-engineer -> ui-test-engineer -> manager`
- High-governance or architecture-sensitive work:
  `manager -> analyst -> architect -> planner -> implementation -> qa-engineer -> architecture-reviewer -> manager`
- Extensibility-sensitive or low-blast-radius work:
  `manager -> analyst -> architect -> planner -> implementation -> qa-engineer -> architecture-reviewer -> manager`
- UX-sensitive user-facing work:
  `manager -> analyst -> architect -> planner -> frontend-engineer -> qa-engineer -> ux-reviewer -> manager`
- Accessibility-sensitive user-facing work:
  `manager -> analyst -> architect -> planner -> qt-ui-engineer -> ui-test-engineer -> accessibility-reviewer -> manager`
- Combined critical work:
  `manager -> product-analyst -> analyst -> architect -> algorithm-scientist -> security-engineer -> performance-engineer -> reliability-engineer -> planner -> implementation -> qa-engineer -> architecture-reviewer -> performance-reviewer -> security-reviewer -> manager`

## Stage gates

- After `analyst`: relevant system areas, contracts, constraints, and unknowns are explicit.
- After `architect`: chosen design, rejected alternatives, boundaries, approved extension seams, dependency direction, stable contracts, expected blast radius, failure modes, and test strategy are explicit.
- After `algorithm-scientist`: correctness, complexity, invariants, and algorithmic failure modes are explicit.
- After `computational-scientist`: the scientific model, assumptions, units, discretization or solver strategy, validation criteria, and numerical failure modes are explicit.
- After `security-engineer`: threat model, trust boundaries, required controls, and must-fix constraints are explicit.
- After `performance-engineer`: budgets, methodology, bottlenecks, and blocking performance risks are explicit.
- After `reliability-engineer`: SLOs, failure modes, degradation behavior, observability expectations, and recovery requirements are explicit.
- After `knowledge-archivist`: canonical docs, plans, reports, references, archive locations, and repository-facing links are consistent or explicitly blocked.
- After `planner`: phases, dependencies, file scope, allowed change surface, must-not-break surfaces, checks, and rollback notes are explicit.
- After `planner`: shared or core module changes, if any, are isolated into explicit enabling phases instead of being hidden inside local feature work.
- After implementation: the phase stayed within scope, includes required tests, and reports changed files and risks.
- After `toolchain-engineer`: build graph behavior, packaging, reproducibility expectations, and local or CI parity are validated or explicitly blocked.
- After `qa-engineer`: acceptance criteria, regressions, edge cases, and basic performance acceptance are verified or explicitly blocked.
- After `ui-test-engineer`: Qt UI interaction states, focus behavior, visual regressions, and high-DPI or theme-sensitive regressions are verified or explicitly blocked.
- After `architecture-reviewer`: the implementation still fits the accepted design, preserves cohesion and dependency direction, uses approved seams, and keeps blast radius within the agreed change surface.
- After `performance-reviewer`: performance evidence and methodology are valid and there are no blocking regressions.
- After `security-reviewer`: no blocking security risks remain and must-fix items are closed.
- After `ux-reviewer`: there are no blocking usability, accessibility, or flow-quality issues.
- After `accessibility-reviewer`: there are no blocking keyboard, focus, labeling, contrast, or assistive-technology issues for the scoped surface.
- After the human or CI gate: required approvals and automated checks are complete.

## Builder and blocker separation

- `product-analyst` and `analyst` gather facts.
- `architect`, `algorithm-scientist`, `computational-scientist`, `security-engineer`, `performance-engineer`, and `reliability-engineer` define constraints and recommendations.
- `knowledge-archivist`, `backend-engineer`, `frontend-engineer`, `graphics-engineer`, `visualization-engineer`, `geometry-engineer`, `qt-ui-engineer`, `model-view-engineer`, `data-engineer`, `toolchain-engineer`, and `platform-engineer` implement approved phases.
- `qa-engineer` and `ui-test-engineer` verify correctness and regressions in their scope.
- `architecture-reviewer`, `performance-reviewer`, `security-reviewer`, `ux-reviewer`, and `accessibility-reviewer` act as independent blockers when their risk domain matters.
- `consultant` is advisory-only and not part of the blocker chain.

Do not let a role that defines a critical constraint act as the only approval gate for that same risk.

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

- canonical brief
- product brief, if used
- research memo
- design doc or ADR
- algorithm note, if used
- computational model package, if used
- security design package, if used
- performance package, if used
- reliability design package, if used
- phase plan
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
