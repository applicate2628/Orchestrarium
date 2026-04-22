# Policy Rules

- Maintain exactly one primary task: X1/X3 lane-fit hardening by waves.
- Source of truth is current live surfaces, not stale or archived score rows.
- Diagnostic rubrics may influence role-fit reads but do not become routing lanes by themselves.
- `$lead` owns the next wave admission and materialization.
- `$qa-engineer` gates after bundle/verifier/scorer/reference validation.
- `$architecture-reviewer` gates only after a routing-policy surface materially changes.
- Calibration rows are bounded by lane impact and route health.
- Runtime, quota, wrapper, missing-summary, and provider tool-loop failures are not model verifier failures.
