# Scoring Anchors

Binary gate over a hidden-derivation oracle. PASS requires ALL of:

1. Bundle shape and scenario.yaml metadata match the contract exactly.
2. Memo carries all required sections, the exact required phrases, the readiness-trace table header, and
   no disallowed marker.
3. Witness `tie_break_rule`, `phase_order`, `first_item`, and `critical_path_length` equal the values
   re-derived from the explicit edges plus the derived edge.
4. Witness `derived_dependencies` includes every derived edge (here: c-cache depends on d-auth).

## Correct answer (re-derived; shown for calibration only)

- phase_order: a-schema, b-api, d-auth, c-cache, e-ui, f-tests, g-docs, h-rollout
- first_item: a-schema
- critical_path_length: 5
- derived edge: c-cache depends on d-auth (constraint C1)

## Failure vs route separation

- An explicit-only order (c-cache before d-auth) FAILs on `witness-phase-order` and
  `witness-missing-derived-edge` - a real model-quality FAIL, not a route/runtime error. A blank
  candidate FAILs on the start-state ids. A malformed witness yields `witness-json-invalid`.
