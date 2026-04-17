# S01 Product Manager Roadmap Prioritization

`S01` benchmarks `R01 $product-manager` on making one owner-level roadmap decision from accepted
intake under conflicting product constraints. The candidate is not asked to do new discovery, write
an analyst brief, provide consultant-style advice, route work as `$lead`, or produce implementation
artifacts.

## Scenario summary

The benchmark redesign already has twenty completed v2 roots, an accepted fourth-wave plan, and a
known final remainder wave after that. Stakeholders want visible progress quickly, but there is
only one clean rerun window before public preview pressure, and the quality gates require
integration, QA, and architecture review before any externally credible rerun or publication.

The correct role behavior is to choose the next two roadmap priorities, make the admission order
explicit, defer lower-value asks, and explain the sequencing guardrails without turning the packet
into product analysis, advisory tradeoff writing, orchestration recovery, or implementation work.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/roadmap-decision-package.md`

Use only the accepted packet in `inputs/`. The completed roadmap decision package must:

- stay product-manager-owned and decision-oriented
- set explicit `Priority 1` and `Priority 2` roadmap items
- defer lower-priority asks with clear re-entry triggers
- ground the roadmap in launch, capacity, gate, and rerun-window constraints
- preserve the boundary against product-analysis, consultant, lead-routing, and implementation drift
- end with one decision status:
  - `APPROVED FOR ROADMAP`
  - `REQUIRES RE-INTAKE`
  - `BLOCKED BY MISSING CONSTRAINTS`

## What this bundle tests

- owner-level prioritization instead of neutral option comparison
- roadmap sequencing under conflicting launch, coverage, and budget pressure
- explicit deferral discipline instead of backlog dumping
- role fidelity for `$product-manager` rather than `$product-analyst`, `$consultant`, `$lead`, or
  an implementer

## Bundle map

- `inputs/` holds the accepted intake summary, initiative cards, constraint ledger, and decision
  rules
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the preferred roadmap ordering, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed roadmap-package structure
