# Phase 03 - Review Response

Fresh worker session. Resume from the files already changed. Read `inputs/review-feedback.md`.

Handle the review packet in `candidate/review-response.json` and update tests or source only if the
review exposes a real remaining defect.

Required decisions:

- accept `R1-stable-idempotency`
- accept `R2-report-source`
- accept `R3-tests-cover-stale-profile`
- reject `R4-ui-badge-decoy`
- reject `R5-legacy-helper-decoy`

Each response must include an owner path and a validation cue. Do not edit `legacy/`, `ui/`,
`inputs/`, `oracle/`, or `verifiers/`.
