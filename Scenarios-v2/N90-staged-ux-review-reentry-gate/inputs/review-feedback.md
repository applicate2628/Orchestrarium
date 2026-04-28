# Author Response Set

Classify each response as `accept`, `revise`, or `reject`.

- `A1-stale-source-advisory`: stale remote source is only advisory; backend conflict handling is enough.
- `A2-regression-proof-required`: missing or pending regression proof should block publish until proof is visible.
- `A3-owner-first-priority`: when owner and stale source are both present, owner assignment should remain the first remediation.
- `A4-mobile-disabled-publish-first`: mobile may keep disabled publish above remediation actions because disabled buttons are harmless.
- `A5-redact-auditor-export`: auditor export should remove owner-only notes and internal resolution notes.
- `A6-follow-up-reentry-block`: follow-up diffs after publish should keep the receipt visible and require evidence review before reentry.
- `A7-disabled-opacity-bug`: the disabled button opacity style is a UX accessibility defect on its own.
