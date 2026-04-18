# N04 Regression Triage Gate

`N04` benchmarks `R25 $qa-engineer` on a generic pre-PR regression-triage lane over a mixed packet
of recent changes and evidence. The candidate does not patch code, produce a QA acceptance matrix,
or drift into architecture, security, or performance review. The only editable surface is one
triage report.

## Scenario summary

A small status-snapshot tool picked up three recent pre-PR changes across the dry-run path, footer
summary wording, and alert-digest dedupe. The packet also includes targeted test results, smoke
notes, operator signals, stable nearby checks, and a small amount of pre-existing noise.

The correct outcome is not implementation guidance. It is a prioritized triage read that:

- treats dry-run state mutation as the top likely regression
- treats the `--only-failed` footer count mismatch as a major regression
- treats duplicate `ops-summary` notifications as a major regression
- records stable nearby surfaces and deprioritizes the pre-existing noise

## Expected candidate work

Edit only `candidate/regression-triage-report.md`.

Use the immutable packet in `inputs/`. The completed triage report must:

- order likely regressions by priority with severity anchors
- cite review-target files and the supplied evidence notes
- distinguish stable nearby surfaces from actual regressions
- deprioritize the pre-existing flake and lint noise instead of promoting them to regressions
- stay triage-only and end with a gate decision of `REVISE`

## What this bundle tests

- mixed-evidence regression triage on a bounded pre-PR packet
- prioritization instead of generic bug dumping
- evidence-backed separation of likely regressions from stable or noisy signals
- review-only discipline for a `P06` regression gate

## Bundle map

- `inputs/` holds the task contract, recent-change packet, evidence notes, stable signals, and
  read-only changed files
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the ground-truth regressions, report boundary, and scoring anchors
- `verifiers/` contains a local checker for the bundle contract and a completed triage report
