# Scoring Anchors

`S25` uses the shared `review, QA` profile.

## Strong-pass signals

- every acceptance criterion is mapped to cited evidence
- the report separates the dry-run regression from the nearby smoke gap
- the performance smoke is acknowledged as a pass without over-escalation
- the verdict stays QA-only and ends with an explicit gate decision

## Material deductions

- missing acceptance-to-evidence mapping
- misclassifying the dry-run defect as `contract-change` or `test-rot`
- ignoring the `--text-summary` smoke gap
- proposing code patches or architecture redesign instead of a QA verdict
- omitting the bug-registry expectation after a non-pass verdict
