Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This is the upgraded retrofit fixture for `T10 / legacy M10`.

It turns the old prompt-only resume lane into a runnable local fixture with:

- explicit broken-state and control-pass copies
- one allowed output seam
- stale-context rejection pressure
- anti-drift checks on the accepted source artifacts

## Goal

Write the correct orchestration resume memo into:

- `workspace/resume-memo.md`

using only the supplied local artifact files.

## Allowed output seam

Only this file should be rewritten:

- `workspace/resume-memo.md`

Do not rewrite the accepted or stale source artifacts under `workspace/artifacts/`.

## Verification

Run both commands from inside either copy's `workspace/` root:

- `node --test`
- `node scripts/verify-resume-memo.js`

The fixture is valid only when:

1. the `broken/` copy fails both checks
2. the `control-pass/` copy passes both checks
3. the memo resumes from the current accepted state
4. stale context is explicitly rejected instead of blended in
5. the output stays inside the admitted benchmark scope
6. source artifacts stay unchanged
