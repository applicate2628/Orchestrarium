# S07 Architect Multi-Seam ADR

`S07` benchmarks `R07 $architect` on choosing the right extension seam for a design-bundle
architecture problem when multiple seams look plausible. The candidate is not asked to gather new
repo facts, write implementation code, or turn the task into a delivery plan. The scored behavior
is to produce one role-correct ADR or design package from the accepted research packet.

## Scenario summary

The benchmark system already has a fixed universal bundle contract, a fixed scoring-profile model,
and an accepted Phase 2 requirement that `S07` stay a design-packet bundle. The open design
question is where scenario-specific seam-choice and tradeoff anchors should live for architect
bundles without reopening taxonomy, scoring, or path conventions.

Three seams are intentionally plausible:

- enrich the universal `scenario.yaml` contract
- localize the design contract in bundle-local `oracle/` and `verifiers/`
- centralize the logic in the global scorer or role registry

The candidate must choose one seam, justify the dependency direction, reject the others, and keep
the result inside one ADR or design package.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/design-package.md`

Use only the accepted research packet in `inputs/`. The completed design package must stay
architecture-focused and include:

- a chosen approach and explicit alternatives
- boundaries, protected surfaces, and approved extension seams
- dependency direction and stable contracts
- failure modes, observability, security-by-design, and test strategy
- a numbered claims section for downstream review
- one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

## What this bundle tests

- turning accepted research into a durable architecture decision
- choosing an additive seam instead of widening into global scoring or metadata churn
- protecting global contract surfaces while still making the bundle self-contained
- keeping design work separate from implementation and planning
- writing reviewable claims that an architecture reviewer can verify later

## Bundle map

- `inputs/` holds the accepted brief, factual memo, seam options, and dependency map
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the admissible seam, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed design-packet structure
