# Scoring Anchors

- Must choose `agents-mode loader normalization`.
- Must mark `externalPriorityProfiles` plural as authoritative.
- Must mark `externalPriorityProfile` singular as stale compatibility input, not source of truth.
- Must keep `X4` secret-backed Claude as a runtime route constraint, not a profile key.
- Must name all four concrete evidence source paths in the evidence ledger.
- Must mention `providerRoutes` for route-state separation.
- Must state the forbidden dependency direction: adapters must not parse or infer lane/profile policy.
- Must include a migration and regression-test section covering singular compatibility input, plural output,
  `providerRoutes`, `X4` non-profile status, and adapter contract boundaries.
- Each claim must include `Verification:` and `Regression:` text.
- Must include a parseable machine decision JSON object matching the contract invariant exactly.
