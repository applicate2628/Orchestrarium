# N89 Security Runtime Witness Review Gauntlet

`N89` benchmarks `$security-reviewer` on a multi-file security review gate that requires exact
binding to executable witness outcomes, not just finding tuples or prose reproduction claims. The
candidate does not patch code, rewrite the system, or turn the task into a worker bundle.

## Scenario Summary

An internal admin, webhook, session, and export bundle reached the security review lane after
implementation. The team claims tenant scope, role checks, webhook verification, session handling,
and export links are safe. The review must map each real vulnerability to a repro case and to the
runtime witness row that a deterministic harness would observe, while excluding benign probes.

## Expected Candidate Work

Edit only `candidate/review-report.json`.

Use the immutable materials in `inputs/` together with the read-only review target in
`candidate/review-target/`. The correct outcome is a findings-first security report that:

- identifies all nine seeded vulnerability tuples
- binds every finding to the correct `R*` reproduction case and violated invariant
- adds a `witnessMatrix` row for every `R1..R9` exploit and `B1..B3` benign probe
- preserves exact file, line, category, severity, source evidence, and observed impact
- avoids synthetic-token, noopener, and public-health-endpoint false positives with benign witness
  rows
- ends with a gate decision of `REVISE`

## What This Bundle Tests

- security depth across authz, tenant boundary, sessions, webhooks, secret exposure, and PII
- exact source binding, executable witness binding, and severity discipline
- false-positive control under realistic-looking harmless details
- review-only separation for unresolved `L10` security routing

## Bundle Map

- `inputs/` holds the task contract, accepted security claims, notes, and review boundary
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth findings, runtime witness expectations, severity anchors,
  false-positive traps, and scoring read
- `verifiers/` contains a local checker plus deterministic witness harness for the completed report
