# Admissible Seams

## Strong-pass seam

`Option B - bundle-local oracle and verifier seam`

This is the admissible seam because it satisfies all accepted constraints simultaneously:

- leaves the universal `scenario.yaml` contract unchanged
- keeps the scenario self-contained inside the bundle root
- matches the worked-example expectation that `oracle/` and `verifiers/` anchor seam choice,
  tradeoff coverage, and dependency-direction claims
- preserves the shared design score profile instead of inventing a new one
- keeps the candidate change surface limited to a design packet only

## Plausible but non-admissible seams

### `Option A - scenario.yaml enrichment seam`

This looks attractive because it centralizes metadata, but it breaks the accepted contract by
changing the universal `scenario.yaml` field set. A candidate who chooses this seam must lose
correctness and scope-discipline points unless they explicitly return `BLOCKED` on the upstream
contract conflict.

### `Option C - central scorer rule seam`

This looks attractive because it centralizes enforcement, but it puts scenario-local architect
semantics into a global scorer. That widens blast radius, weakens bundle self-containment, and
makes the scorer depend on architecture-specific prose it should not own.
