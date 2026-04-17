# Regression Classification

## Real defect

- issue: `--dry-run` still writes `status.snapshot.json`
- classification: `regression`
- owner action: implementer fixes the write-order bug and QA re-verifies

## Why this is not another class

- not `contract-change`: the accepted phase plan and acceptance criteria still require dry-run to
  avoid writes
- not `test-rot`: the existing dry-run test is incomplete, but the product behavior still violates
  the intended contract in direct smoke evidence

## Separate coverage gap

The missing `--text-summary` smoke is an explicit nearby coverage gap. It is not itself a
`contract-change` or `test-rot` classification, but it should still be called out as a gate-holding
evidence gap on a must-not-break surface.
