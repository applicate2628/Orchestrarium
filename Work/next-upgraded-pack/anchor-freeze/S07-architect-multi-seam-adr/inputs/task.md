Role: `$architect`
Goal: Produce the design package for how v2 architect bundles should encode scenario-specific seam
choice and tradeoff anchors without reopening the universal scenario contract.

Approved inputs:
- `inputs/accepted-brief.md`
- `inputs/factual-repo-memo.md`
- `inputs/competing-seam-options.md`
- `inputs/dependency-map.md`

Allowed tools:
- read the approved inputs
- edit only `candidate/design-package.md`

Scope:
- choose the owning seam for design-specific bundle rules
- document alternatives and tradeoffs
- define boundaries, approved extension seams, and dependency direction
- specify stable contracts, failure modes, observability, security-by-design, and test strategy
- write numbered claims that an architecture reviewer can check later

Out of scope:
- implementation code, scripts, or config patches
- planner phase sequencing
- taxonomy, score-profile, or path-convention changes
- new research beyond the accepted packet

Must-not-break surfaces:
- the universal `scenario.yaml` field contract
- the accepted scoring-profile model
- pack separation between semantic roles and adapters
- the design-bundle identity that the candidate edits only a design packet

Expected artifact:
- one ADR or design package in `candidate/design-package.md`

Acceptance criteria:
- the package is role-correct for `$architect`
- the chosen seam is justified against at least two realistic alternatives
- dependency direction and protected surfaces are explicit
- the design remains self-contained and does not turn into an implementation or planning artifact

Gate to next stage:
- a planner or architecture reviewer can consume the package without reinterpreting the decision
