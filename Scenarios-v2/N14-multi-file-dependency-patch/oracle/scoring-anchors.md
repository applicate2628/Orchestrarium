# Scoring Anchors

PASS requires:

- exact oracle behavior for all `behavior-cases.json` cases
- changed paths restricted to the allowed surface
- no candidate source hardcoding of oracle case IDs or oracle JSON paths
- non-scoreable route/runtime rows rendered as caveats, not scoreable failures

FAIL signals:

- stale singular profile field overrides the active plural profile catalog
- timeout, quota, route-unavailable, stdin-deadlock, or missing-worker-output rows counted as `FAIL`
- denominator includes non-scoreable rows
- report has no visible caveat line for non-scoreable rows
- patch moves behavior into tests, UI labels, legacy helpers, oracle, or verifier files
