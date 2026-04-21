Review the bounded share-dialog target and produce a findings-only UX report.

The report must identify the highest-severity comprehension or flow issues, cite exact bundle-local
evidence, and end with a gate decision. Do not patch code or rewrite the feature as a design brief.

Hardening requirements:

- report exactly three findings
- each finding must be a separate bullet and include `Evidence:`, `Impact:`, `Recommendation:`,
  and `Regression:` labels
- include `## Evidence-To-Finding Ledger` with columns `Finding`, `Bundle-local evidence`,
  `User impact`, and `Severity reason`
- include `## False Positives Avoided` as a table with columns `Decoy`, `Why not a finding`, and
  `Boundary cue`
- preserve the boundary between UX review output and implementation: do not edit reviewed code,
  propose route/API/storage mechanics, or produce a design brief
