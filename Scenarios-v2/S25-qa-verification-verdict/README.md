# S25 QA Verification Verdict

`S25` benchmarks `R25 $qa-engineer` on an evidence-backed verification gate for a bounded
implementation change. The candidate does not patch code, redesign the feature, or review
architecture. The only editable surface is a QA verdict report.

## Scenario summary

An implementation phase added JSON output and a `--dry-run` mode to a bundle-local status snapshot
tool. The accepted phase plan required explicit acceptance mapping, nearby smoke coverage for the
existing text path, and a basic performance smoke. The supplied evidence shows one real regression
and one missing nearby smoke check.

## Expected candidate work

Edit only `candidate/qa-verdict.md`.

Use the immutable materials in `inputs/` to produce a QA report that:

- maps every acceptance criterion to evidence or an explicit gap
- distinguishes an observed regression from missing coverage
- records nearby smoke status for must-not-break surfaces
- includes the basic performance smoke result without escalating it into a separate review lane
- states the bug-registry expectation that follows from the verdict
- ends with one explicit gate decision

## What this bundle tests

- acceptance-criteria mapping instead of generic commentary
- QA-only scope discipline for a `P06` bundle
- nearby smoke coverage on adjacent surfaces
- explicit regression classification
- evidence-backed `PASS` or `REVISE` verdict writing

## Bundle map

- `inputs/` holds the task contract, accepted phase plan, diff, and executed verification evidence
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth QA outcome, regression classification, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and a completed QA report
