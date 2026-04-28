# N81 Evidence Conflict Repo Action Plan

`N81` benchmarks repo-understanding under conflicting current code, tests, command output, accepted ADRs,
stale docs, and a draft rollback ADR. The candidate must produce a bounded repo action plan, not a
runtime patch and not a product decision.

## Scenario Summary

The RetryBox snapshot has current runtime code and passing unit tests for `retry-policy-v3`, while
old documentation still describes `legacy-linear`. A docs check fails because the docs are stale.
The correct response separates authoritative current evidence from stale or draft evidence, chooses
documentation/evidence sync as the immediate action, and names the product re-intake boundary for
semantic changes.

## Expected Candidate Work

Edit only `candidate/action-plan.md`.

The correct output:

- ranks five sources by authority
- resolves six evidence conflicts
- records three command outputs and their implications
- gives four bounded action-plan rows
- names five non-claims
- states the re-intake trigger for retry, owner, or customer-visible export semantics

## Bundle Map

- `inputs/` holds the task contract and source-authority rules
- `candidate/repo-snapshot/` is the read-only repository snapshot
- `oracle/` defines the required source ranking, conflict ledger, command evidence, action rows, and scoring
- `verifiers/` contains the local checker for the bundle contract and completed action plan
