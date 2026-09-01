# Competing Seam Options

All three options are plausible at first glance. The architect must decide which seam is acceptable
under the admitted constraints.

## Option A - scenario.yaml enrichment seam

Add new fields to `scenario.yaml` such as:

- `admissible_seams`
- `required_tradeoff_anchors`
- `dependency_direction_claims`

### Benefits

- single metadata file advertises more of the bundle contract
- central tooling can discover design-specific rules without opening `oracle/`

### Costs

- reopens the universal field contract defined in `pack-specs-v1`
- turns role-specific design semantics into global metadata
- forces review of path and schema conventions outside the admitted scope

## Option B - bundle-local oracle and verifier seam

Keep `scenario.yaml` unchanged. Add a design-specific contract in `oracle/` and let the bundle's
local verifier check the candidate design packet against that contract.

### Benefits

- additive and local to the `S07` bundle
- matches the accepted worked-example expectation that oracle and verifiers anchor seam choice and
  dependency-direction claims
- keeps the scoring-profile model unchanged
- preserves the design-bundle identity that only the design packet is mutable

### Costs

- each design bundle owns its own design-contract file
- cross-bundle analysis would need a later aggregation layer if ever required

## Option C - central scorer rule seam

Teach the global scorer or role registry to parse architect design packages directly and enforce the
required seam and tradeoff rules from one central place.

### Benefits

- one place to implement design-bundle comparisons
- fewer bundle-local verifier rules if all architect scenarios were identical

### Costs

- pushes scenario-local design semantics into a global scorer
- increases cross-cutting blast radius for every new architect scenario
- weakens bundle self-containment and hides the role-specific contract away from the bundle root
- encourages the scorer to depend on scenario-local architecture language instead of stable outputs
