# N66 Conflicting Evidence Fact Memo Gauntlet

`N66` benchmarks repo-understanding under conflicting sources. The candidate must write a fact memo
that ranks source authority, resolves stale/draft evidence against current code and tests, names
non-claims, and chooses a bounded next action.

## Scenario Summary

A BillingMesh policy migration left current code, tests, accepted ADRs, stale README text, a draft
ADR, and a mixed migration note in conflict. The memo must not patch code or pick a product policy
by preference. It must identify the current source of truth and separate verified facts from stale
or proposed material.

## Expected Candidate Work

Edit only `candidate/fact-memo.md`.

The correct output:

- ranks source authority explicitly
- resolves five conflicting claims with source-bound evidence
- confirms four current facts from code/tests/accepted ADRs
- names four non-claims to prevent stale-source drift
- chooses a bounded documentation cleanup plus re-intake path for semantic changes

## Bundle Map

- `inputs/` holds the task contract and source-authority rules
- `candidate/repo-snapshot/` is the read-only repository snapshot
- `oracle/` defines the expected source ranking, conflict ledger, facts, non-claims, and scoring
- `verifiers/` contains a local checker for the bundle contract and completed fact memo
