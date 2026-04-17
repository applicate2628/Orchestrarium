# S09 Planner Phased Delivery Plan

`S09` benchmarks `R09 $planner` on turning an accepted brief, accepted design package, and
accepted constraints into one bounded phase plan. The candidate is not asked to gather new
repository facts, reopen the design choice, or create an implementation workspace.

## Scenario summary

The bundle models an additive delivery task for a bundle-local status snapshot tool. Upstream work
has already accepted:

- the product brief for adding machine-readable JSON output and a `--dry-run` preview mode
- the design seam that keeps the change inside the tool owner and its direct tests
- the delivery constraints, protected surfaces, required checks, and rollback expectations

The correct planner behavior is to sequence the work into ordered phases with explicit file scope,
dependencies, tests and checks, rollback notes, and downstream gates.

## Expected candidate work

Edit only the file listed in `scenario.yaml`:

- `candidate/phase-plan.md`

Use only the accepted packet in `inputs/`. The completed plan must:

- stay planner-owned and plan-only
- cite the accepted upstream inputs instead of redoing research or design
- present ordered phases with explicit file scope
- state dependencies, tests and checks, and rollback notes for each phase
- keep implementation code, diffs, and execution transcripts out of the artifact
- end with one explicit gate decision: `PASS`, `REVISE`, or `BLOCKED`

## What this bundle tests

- phased delivery planning from accepted upstream artifacts
- separation between planning, research, design, and implementation
- file-scope discipline and bounded rollback thinking
- verification planning before implementation starts
- role fidelity for `$planner` rather than `$analyst`, `$architect`, or an implementer

## Bundle map

- `inputs/` holds the accepted brief, accepted design, accepted constraints, and task contract
- `candidate/` is the mutable run root copied per execution
- `oracle/` defines the expected phase order, anti-patterns, and scoring anchors
- `verifiers/` contains a local checker for bundle shape and completed phase-plan structure
