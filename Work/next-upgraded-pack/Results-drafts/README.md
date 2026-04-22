Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This directory is reserved for draft result surfaces for the next upgraded pack.

Draft results here must not overwrite the archived snapshot.
Only admitted later packages should become new dated snapshots under `Archive/`.

## Current draft surfaces

| File | Role |
|---|---|
| `x1-x3-steady-state-core-results-2026-04-17.md` | legacy admitted steady-state core result surface |
| `x1-x3-current-runnable-pack-results-2026-04-17.md` | legacy supporting runnable-pack surface |
| `x1-x3-full-registry-results-2026-04-17.md` | legacy widest execution-backed registry surface for `X1..X3` |
| `v2-worked-example-cohort-results-2026-04-18.md` | first admitted bounded v2 result surface for `X1`, `X2`, `X5`, and `X6` |
| `v2-full-s01-s33-results-2026-04-18.md` | earlier same-day full v2 result surface on `S01..S33` only |
| `v2-full-s01-s33-n01-n07-results-2026-04-18.md` | current quota-aware full v2 result surface for `X1`, `X2`, `X3`, `X4`, `X5`, and `X6` on `S01..S33 + N01..N07`; `X5/S12` reran into scoreable `FAIL` |
| `v2-extra-lane-n08-n10-results-2026-04-20.md` | reference extra-lane result surface for `E1 worker.long-autonomous`; `X4` is `NOT-RUN` while the secret-backed Claude route is unavailable |
| `v2-core12-tie-hardened-results-2026-04-20.md` | targeted hardening result for weak-separator core lanes; `X1` and `X3` tied, `X5` separated lower with timeout caveats |
| `v2-top-pair-separators-n11-n13-results-2026-04-20.md` | diagnostic `E2` result; initial and hardened2 runs still tie `X1` and `X3` |
| `v2-top-pair-rubric-e3-results-2026-04-20.md` | diagnostic E3 rubric over fresh 2026-04-21 `N11..N13` outputs; narrow `X1 60 / 60` vs `X3 59 / 60` read |
| `role-fit-scorecard-v1-2026-04-22.md` | current lane-fit routing read; maps `X1`/`X3` plus calibration rows to role/lane recommendations, with compactness-only winners marked `provisional-primary` |
| `../Planning/next-phase/hardening-wave-roadmap-2026-04-22.md` | live roadmap for subsequent hardening waves and spawn usage |
| `../Evidence/n17-owner-routing-rubric-2026-04-22.json` | machine-readable E7 owner/orchestration calibration read for `X1`, `X2`, `X3`, and `X6` |
| `../Evidence/n18-scientist-constraints-rubric-2026-04-22.json` | machine-readable E8 scientist/constraints calibration read for `X1`, `X2`, `X3`, `X5`, and `X6` |
| `../Evidence/n19-systems-toolchain-rubric-2026-04-22.json` | machine-readable E9 systems/toolchain calibration read for `X1`, `X2`, `X3`, and `X6` |
| `../Evidence/n20-ui-interaction-rubric-2026-04-22.json` | machine-readable E10 UI interaction calibration read for `X1`, `X2`, `X3`, and `X6` |
| `../Evidence/n21-visual-raster-rubric-2026-04-22.json` | machine-readable E11 visual-raster calibration read for `X1`, `X2`, `X3`, `X5`, and `X6` launch attempts |
| `../Evidence/n22-numerical-stability-rubric-2026-04-22.json` | machine-readable E12 numerical-stability calibration read for `X1`, `X2`, `X3`, and `X6` |
| `../Evidence/n23-owner-recovery-rubric-2026-04-22.json` | machine-readable E13 owner-recovery calibration read for `X1`, `X2`, `X3`, and `X6` |
| `../Evidence/n24-toolchain-repeat-rubric-2026-04-22.json` | machine-readable E14 systems/toolchain repeat read for `X1`, `X2`, `X3`, `X5`, and `X6`; confirms systems/toolchain `X3 primary` |
| `short-results-current-2026-04-18.md` | compact operator-facing short table for the current six-row live state |
