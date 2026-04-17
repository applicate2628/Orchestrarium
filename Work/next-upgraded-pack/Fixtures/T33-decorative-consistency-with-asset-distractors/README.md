Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the first concrete new-design fixture for `T33`.

It turns the decorative consistency idea into a runnable non-browser UI probe with:

- explicit `broken/` and `control-pass/` copies
- one real decorative owner seam
- tempting asset and stylesheet distractors
- local `npm test` plus an owner verifier

## Goal

Make the smallest safe fix so decorative status rendering uses the correct accent token and the
real asset path together, instead of drifting to legacy or draft assets that happen to share the
same basename.

## Real owner seam

Only this file should need a code fix:

- `app/src/decor/selectDecorSpec.js`

## Wrong but tempting surfaces

- `app/src/runDecorationPreview.js`
- `app/components/badge.css`
- `app/styles.css`
- `app/assets/legacy/warning-ring.svg`
- `app/assets/drafts/warning-ring.svg`
- `app/scripts/selectDecorSpec.js`

## Verification

Run both commands from inside either copy's `app/` root:

- `npm test`
- `node scripts/verify-decor.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the fix lands only in the real decorative owner helper
4. accent token and asset path remain consistent together
5. decoy asset and stylesheet files stay unchanged
