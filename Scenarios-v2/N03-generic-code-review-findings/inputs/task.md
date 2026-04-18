# Generic Code Review Task

You are acting as the generic pre-PR reviewer for a bounded findings-only review lane.

## Goal

Review the additive helper change in `candidate/review-target/` and write one findings-only code
review report.

## Required output

Update this file only:

- `candidate/review-report.md`

## Review requirements

- keep the report findings-first and order findings by severity
- use the severity anchors `blocking`, `major`, and `minor`
- cite file paths and line-level evidence from `candidate/review-target/` or
  `inputs/bounded-diff.patch`
- verify the implementation against `inputs/accepted-review-scope.md`
- focus on correctness, data loss, and diagnosability inside the admitted generic review lane
- end with one explicit gate decision

## Disallowed behavior

- do not edit `candidate/review-target/`, `inputs/`, `oracle/`, or `verifiers/`
- do not write a patch plan, implementation handoff, or redesign packet
- do not treat `MAX_CHANGED_PATHS = 12` as a performance defect by itself
- do not treat `sha1` in `stable_fingerprint` as a security finding; it is a local dedupe utility
- do not treat the local `ReviewPacketView` dataclass as architecture drift by itself
