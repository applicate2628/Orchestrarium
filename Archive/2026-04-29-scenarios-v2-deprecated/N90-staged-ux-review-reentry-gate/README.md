# N90 - Staged UX Review Reentry Gate

Diagnostic hardening bundle for UX review role-fit separation.

The candidate must review a small publish-console runtime under
`candidate/review-target/` and produce staged review artifacts only. The
review target is intentionally flawed but protected by the verifier.

The verifier checks:

- exact protected hashes for all review-target files
- exact changed-path scope
- source-bound staged review state
- opaque exact finding tuples
- runtime witness rows for exploit and benign UX cases
- false-positive rejection
- response-gate and reentry closeout completeness
