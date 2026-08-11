# Implementation

Gate: PASS

## Root cause

Commit `3bf83684` added the bounded Claude dispatch sentinel and marked the observer-gap bug fixed. Physical lifecycle later moved that fixed record to `work-items/bugs/archive/2026-08/`, but five live review-loop surfaces and `tests/test_review_loop_state_v2.py` still named the old open path and described the defect as open.

## Change

- Replaced the five stale live relations with the archived record path and current provider/helper boundary.
- Kept the state helper's honest limitation: it does not observe direct/ad-hoc bypass.
- Kept Claude's bounded internal Agent dispatch observation explicit without extending that guarantee to Codex or arbitrary launch paths.
- Updated the owning test to require the archived record and reject the former live path across all five surfaces.

## Verification

- Durable RED: exact owner test failed on the first stale live path.
- Full review-loop state: 34 passed.
- Dispatch sentinel: 18 passed, 10 subtests passed.
- Codex pack: 530/530 PASS.
- Claude pack: 449/449 PASS.
- Live stale-path scan: zero hits outside the deliberate negative test literal.
- `git diff --check`: PASS.

## Rollback

Reset the isolated quick-fix commit before publication; no schema, runtime state, installer, or production behavior changed.

## Terms and Abbreviations

- **Observer gap:** the historical inability of the ledger helper alone to detect a loop that never invoked it.
- **Current truth:** live documentation describing only the presently valid relationship.
