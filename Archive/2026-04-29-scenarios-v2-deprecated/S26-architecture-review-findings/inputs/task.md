# Task

You are acting as `$architecture-reviewer` on a bounded review phase.

## Goal

Review the additive `P06` bundle materialization change in `candidate/review-target/` and write a
findings-only architecture review report.

## Required output

Update this file only:

- `candidate/review-report.md`

## Review requirements

- keep the report findings-first and order findings by severity
- use the severity anchors `blocking`, `major`, and `minor`
- cite file paths and line-level evidence from `candidate/review-target/` or
  `inputs/bounded-diff.patch`
- verify the accepted claims in `inputs/accepted-design.md` against the changed files
- call out maintainability, boundary, and governance drift that requires `REVISE`
- keep the report review-only; do not add a repair plan, patch sketch, or implementation handoff

## Disallowed behavior

- do not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`
- do not propose code changes as deliverables
- do not treat `overlay_flags: []` as a defect
- do not treat the local `SEVERITY_LABELS` tuple as architecture drift by itself
- do not invent security or performance findings without an architectural basis in this bundle
