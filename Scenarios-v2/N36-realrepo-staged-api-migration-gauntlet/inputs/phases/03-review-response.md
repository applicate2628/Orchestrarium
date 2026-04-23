# Phase 03 - Review Response

Fresh worker session. Resume from the files already changed. Read `inputs/review-feedback.md`.

Handle the review packet in `candidate/review-response.json` and update tests or source only if the
review exposes a real remaining defect.

Required decisions:

- reject `R1-legacy-shim-request`
- accept `R2-denied-usage-no-publish`
- accept `R3-owner-boundary`
- accept `R4-report-queued-duplicate`
- reject `R5-doc-only-decoy`
- accept `R6-read-feature-boundary`

Each response must include an owner path and a validation cue. Do not edit `inputs/`, `oracle/`,
`verifiers/`, `candidate/README.md`, or `candidate/workspace/README.md`.
