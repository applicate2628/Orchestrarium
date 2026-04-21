Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Scope

This file admits the targeted timeout-closure pass for `X5 / gemini3.1pro` on the hardened
core-12 weak-separator subset. It only updates the previous timeout / incomplete cells from
`Evidence/x1-x3-x5-core12-tie-hardened-2026-04-20.md`; it does not replace the full-v2
`S01..S33 + N01..N07` surface.

The original isolated Gemini wrapper uses `--prompt=` plus stdin. On `N04` and `N05`, that transport
hung before a normal `summary.json` was written. The closure reran those two scenarios with the same
model, isolated temporary HOME, no MCP, and prompt passed as the `--prompt <text>` argument. This is
recorded separately as a transport workaround, not a scenario or verifier change.

## Closure Results

| Scenario | Previous state | Closure route | Verifier result | Admitted state |
|---|---|---|---|---|
| `N02` | `TIMEOUT artifact-pass` | normal `run-v2-cohort-batch.ps1` runner | `check_interaction_state_flow_brief.py=0` | `PASS` |
| `N03` | `TIMEOUT artifact-fail` | normal `run-v2-cohort-batch.ps1` runner | `check_generic_review.py=1` | `FAIL` |
| `N04` | `TIMEOUT artifact-fail` | isolated Gemini direct-prompt transport | `check_regression_triage.py=0` | `PASS` |
| `N05` | `TIMEOUT artifact-fail` | isolated Gemini direct-prompt transport | `check_secret_exposure_review.py=1` | `FAIL` |
| `N06` | `TIMEOUT artifact-fail` | normal `run-v2-cohort-batch.ps1` runner | `check_authz_trust_review.py=0` | `PASS` |

## Run Roots

| Scenario | Root / output |
|---|---|
| `N02`, `N03` | `.scratch/v2-cohort-runs/2026-04-20_18-28-31-X5-x5-core12-hardened-close-timeouts-n02-n06-2026-04-20/` |
| `N04` | `.scratch/v2-cohort-runs/2026-04-20_19-32-07-X5-x5-core12-hardened-close-timeout-n04-2026-04-20b/`; direct output `N04/meta/worker-output-direct-prompt.txt` |
| `N05` | `.scratch/v2-cohort-runs/2026-04-20_20-03-05-X5-x5-core12-hardened-close-timeout-n05-2026-04-20b/`; direct output `N05/meta/worker-output-direct-prompt.txt` |
| `N06` | `.scratch/v2-cohort-runs/2026-04-20_20-34-09-X5-x5-core12-hardened-close-timeout-n06-2026-04-20b/` |

## Updated X5 Read

| Surface | Before | After |
|---|---:|---:|
| admitted PASS | `9` | `12` |
| admitted FAIL | `1` | `3` |
| timeout / incomplete | `5` | `0` |

## Final X5 Hardened Scenario States

| Scenario | Lane | State |
|---|---|---|
| `S03` | `advisory.repo-understanding` | `PASS` |
| `S04` | `advisory.repo-understanding` | `PASS` |
| `S06` | `advisory.repo-understanding` | `PASS` |
| `S05` | `advisory.design-adr` | `PASS` |
| `S07` | `advisory.design-adr` | `PASS` |
| `S09` | `advisory.design-adr` | `PASS` |
| `S08` | `design.ui-ux-structure` | `PASS` |
| `N01` | `design.ui-ux-structure` | `PASS` |
| `N02` | `design.ui-ux-structure` | `PASS` |
| `S25` | `review.pre-pr` | `FAIL` |
| `N03` | `review.pre-pr` | `FAIL` |
| `N04` | `review.pre-pr` | `PASS` |
| `S27` | `review.security` | `PASS` |
| `N05` | `review.security` | `FAIL` |
| `N06` | `review.security` | `PASS` |

## Verdict

`PASS` - all previous `X5` timeout cells in the hardened core-12 weak-separator subset have been
converted into admitted scoreable states. The updated `X5` read is `12 PASS / 3 FAIL / 0 TIMEOUT`.
