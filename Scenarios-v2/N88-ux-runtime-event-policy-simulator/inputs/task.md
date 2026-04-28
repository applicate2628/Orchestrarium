# Task - UX Runtime Event Policy

Define UX policy artifacts for the ConsoleShip publish flow. Do not implement UI code.

Produce:

- `candidate/runtime-policy.json`
- `candidate/breakpoint-policy.json`
- `candidate/reentry-policy.json`

The policy must cover these source states:

- remote source stale while local checks are green
- owner missing
- risk accepted but regression proof missing
- auditor-only export requested by an auditor
- already published package receives a follow-up diff

The hidden simulator will replay trace permutations, including combinations not listed verbatim in
this task. It will check:

- publish is disabled until source freshness, owner, risk, and regression proof are satisfied
- disabled reasons are visible and owned by the right source state
- auditor-only export does not imply the package is ready to publish
- published receipt remains visible during follow-up re-entry
- desktop, tablet, and mobile breakpoint ordering preserves blocker visibility and action priority

Required policy identifiers:

- actions: `refresh-source`, `assign-owner`, `attach-regression`, `review-follow-up-diff`,
  `publish`, `export-auditor-copy`
- disabled reasons: `remote-source-stale`, `owner-missing`, `regression-proof-missing`,
  `auditor-export-only`
- breakpoints: `desktop-1440`, `tablet-900`, `mobile-390`

The verifier reads files, not final prose.
