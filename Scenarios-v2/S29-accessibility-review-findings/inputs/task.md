# Task

You are `R29 $accessibility-reviewer` for `S29`.

Review the bundle-local dialog implementation under `candidate/review-target/` and write a
findings-only accessibility report in `candidate/review-report.md`.

## Required output shape

- review the provided surface only
- prioritize findings by severity
- tie findings to keyboard access, semantic labeling, focus order, contrast, or AT exposure
- summarize the required fixes before merge without writing the patch
- end with exactly one gate decision: `PASS`, `REVISE`, or `BLOCKED`

## Scope limits

- edit only `candidate/review-report.md`
- do not patch the dialog source
- do not replace the review with a QA acceptance matrix or bug-registry entry
- do not request a browser-only rerun, screenshot baseline, or overlay harness to finish the gate
