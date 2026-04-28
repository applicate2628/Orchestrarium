# N84 Security Repro Review Gauntlet

`N84` benchmarks `$security-reviewer` on a multi-file security review gate that requires exact
source-to-exploit reproduction binding, not just finding tuples. The candidate does not patch code,
rewrite the system, or turn the task into a worker bundle.

## Scenario Summary

An internal admin, webhook, session, and export bundle reached the security review lane after
implementation. The team claims tenant scope, role checks, webhook verification, session handling,
and export links are safe. The review must map each real vulnerability to a provided repro case,
observed impact, and violated invariant, while excluding benign probes.

## Expected Candidate Work

Edit only `candidate/review-report.json`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first security report that:

- identifies all nine seeded vulnerability tuples
- binds every finding to the correct `R*` reproduction case and violated invariant
- preserves exact file, line, category, severity, source evidence, and observed impact
- avoids synthetic-token, noopener, and public-health-endpoint false positives
- ends with a gate decision of `REVISE`

## What This Bundle Tests

- security depth across authz, tenant boundary, sessions, webhooks, secret exposure, and PII
- exact source binding, reproduction binding, and severity discipline
- false-positive control under realistic-looking harmless details
- review-only separation for unresolved `L10` security routing

## Bundle Map

- `inputs/` holds the task contract, accepted security claims, notes, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, severity anchors, false-positive traps, and scoring
  read
- `verifiers/` contains a local checker for the bundle contract and completed report
