# Task

You are acting as a product-analyst. Write a scope-bounded product brief for the accepted problem, and
HOLD the scope boundary against the tempting adjacent asks in the noisy intake.

## Accepted problem

Add a CSV export of the currently-visible results to the existing results table (see
`inputs/bounded-scope.md`).

## Output contract

Edit `candidate/product-brief.md`. It must contain:

- `## Problem Statement` - the accepted problem, scoped (mentions CSV export; does not reframe it as a
  broader reporting feature).
- `## In Scope` - only the accepted in-scope items. It must NOT list any of the parked adjacent asks.
- `## Out Of Scope (Parked)` - every adjacent ask from the intake, explicitly parked with a reason.
- `## Success Criteria` - how the in-scope feature is verified.
- `## Gate Decision` - `PASS`, `REVISE`, or `BLOCKED` on its own line.

## The scope-inflation trap (enforced)

The intake dangles extra export formats, a scheduled/email export channel, and a reporting dashboard.
Pulling any of these into `## In Scope` is scope inflation and fails the brief. Silently dropping them
(not parking them) also fails: they must be explicitly parked with a reason.

## Constraints

- Do not expand the scope beyond the accepted CSV export of visible rows.
- Do not edit `inputs/**`, `oracle/**`, `verifiers/**`, or `candidate/README.md`.
- No code blocks, diffs, or TODO markers; this is a product brief.
