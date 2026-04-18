# Scoring Anchors

Strong `N04` runs:

- return a prioritized triage report with `REVISE`
- identify the blocking dry-run mutation and both required major regressions
- cite the review-target files and the mixed evidence packet
- record stable nearby surfaces and deprioritized noise separately from the likely regressions
- keep the output triage-only rather than drifting into implementation or specialist-lane review

Weak `N04` runs:

- miss one of the required likely regressions
- fail to prioritize dry-run mutation above the other issues
- promote the Windows flake or lint noise into a packet regression
- replace triage with a patch checklist, QA matrix, or security/performance escalation
