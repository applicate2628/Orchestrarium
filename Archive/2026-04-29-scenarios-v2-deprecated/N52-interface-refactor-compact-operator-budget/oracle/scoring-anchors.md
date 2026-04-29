# N52 Scoring Anchors

Score the run as an interface-refactor task, not as a style rewrite.

- Correctness: structured interfaces, hidden consumer behavior, error semantics.
- Migration quality: all call sites migrated, old methods removed, no compatibility shims.
- Evidence: refactor ledger maps old interface to new interface and names validation.
- Patch quality: changed paths stay within the allowed surface and avoid unrelated churn.
- Operator quality: visible worker output stays within the compact review budget.
