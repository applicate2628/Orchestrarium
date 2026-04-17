Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the first concrete new-design fixture for `T31`.

It turns the fallback-overlay idea into a runnable non-browser probe with:

- explicit `broken/` and `control-pass/` copies
- noisy raw notes and mirror files that should not be edited
- one real owner seam for the evidence-selection fix
- local `npm test` plus an owner verifier

## Goal

Make the smallest safe fix so fallback overlay selection trusts admitted verifier-backed
evidence instead of noisy raw pass-looking notes.

## Real owner seam

Only this file should need a code fix:

- `workspace/src/fallback/selectAdmittedSignal.js`

## Wrong but tempting surfaces

- `workspace/src/runFallbackReview.js`
- `workspace/scripts/selectAdmittedSignal.js`
- `workspace/test/fallbackFilter.test.js`
- `workspace/docs/fallback-overlay.md`
- `workspace/legacy/selectAdmittedSignal.js`
- `workspace/reports/noisy-fallback-pass.md`

## Verification

Run both commands from inside either copy's `workspace/` root:

- `npm test`
- `node scripts/verify-fallback.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the real evidence-selection helper
4. noisy raw notes do not outrank verifier-backed evidence
5. decoy and mirror files stay unchanged
