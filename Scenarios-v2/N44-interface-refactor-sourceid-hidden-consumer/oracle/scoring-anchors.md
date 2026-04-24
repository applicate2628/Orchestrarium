# N44 Scoring Anchors

Score the run as an interface-refactor task, not as a style rewrite.

- Correctness: structured interfaces, hidden consumer behavior, error semantics, public source IDs.
- Migration quality: all call sites migrated, old methods removed, no compatibility shims.
- Evidence: refactor ledger maps old interface to new interface, names validation, and records the
  immutable visible-test boundary.
- Patch quality: changed paths stay within the allowed surface and avoid unrelated churn.
