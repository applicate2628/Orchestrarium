Role: `$product-manager`
Goal: Decide the next two roadmap priorities for the benchmark redesign under conflicting launch,
coverage, quality-gate, and rerun-budget constraints.

Approved inputs:
- `inputs/accepted-intake-summary.md`
- `inputs/initiative-cards.md`
- `inputs/constraint-ledger.md`
- `inputs/decision-rules.md`

Allowed tools:
- read the approved inputs
- edit only `candidate/roadmap-decision-package.md`

Scope:
- choose and sequence the next two roadmap priorities
- defer lower-priority asks with explicit re-entry triggers
- ground the decision in the accepted launch, capacity, and rerun constraints
- state the guardrails that keep the roadmap coherent for downstream execution

Out of scope:
- product-analysis discovery or a new product brief
- consultant-style tradeoff advice without a committed decision
- lead routing, stage recovery, or delegation packets
- implementation work, code patches, commands, or verifier edits
- running the rerun or publishing results tables inside this artifact

Must-not-break surfaces:
- the roadmap decision package identity
- the accepted fourth-wave plan as read-only context
- the boundary between product-manager ownership and later analyst, lead, or implementer work

Expected artifact:
- one roadmap decision package in `candidate/roadmap-decision-package.md`

Acceptance criteria:
- the package is role-correct for `$product-manager`
- it names `Priority 1`, `Priority 2`, and explicit deferred items
- it keeps the roadmap grounded in the accepted constraints instead of inventing new discovery work
- it does not drift into advisory, routing, or implementation artifacts

Gate to next stage:
- implementers and the lead can consume the package as the admitted roadmap direction without
  mistaking it for product analysis, consultant advice, or a work-item recovery packet
