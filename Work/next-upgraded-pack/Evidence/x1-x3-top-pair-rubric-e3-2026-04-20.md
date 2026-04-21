Date: 2026-04-21
Owner: `$lead`
Status: `PASS`

## Scope

This evidence covers diagnostic `E3 top-pair-rubric` after the 2026-04-21 in-place hardening wave.

The same fresh five-scenario slice was run for `X1` and `X3`:

| Row | Root |
|---|---|
| `X1 / gpt-5.4` | `benchmarks/.scratch/v2-cohort-runs/2026-04-21_14-43-50-X1-x1-v3-ui-review-e2-hardening-2026-04-21/` |
| `X3 / opus 4.7max` | `benchmarks/.scratch/v2-cohort-runs/2026-04-21_15-00-47-X3-x3-v3-ui-review-e2-hardening-2026-04-21/` |

## Binary Gate Read

| Row | `N02` | `S30` | `N11` | `N12` | `N13` | Binary read |
|---|---|---|---|---|---|---:|
| `X1` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |
| `X3` | `PASS` | `PASS` | `PASS` | `PASS` | `PASS` | `5 / 5` |

The binary gates still do not separate `X1` and `X3`.

## Method

| Boundary | Read |
|---|---|
| scorer | `Tooling/score-top-pair-rubric.py` |
| input | fresh `N11`, `N12`, `N13` artifacts from the roots above |
| model calls | yes, as part of the five-scenario hardened slice |
| verifier impact | none; both rows still pass E2 binary gates |
| routing impact | none; E3 is not a routing lane and must not be copied into `externalPriorityProfiles` |

## Result

| Row | Score | Read |
|---|---:|---|
| `X1 / gpt-5.4` | `60 / 60` | wins E3 by `1` point |
| `X3 / opus 4.7max` | `59 / 60` | below X1 on E3 |

## Scenario Scores

| Scenario | X1 | X3 | Delta |
|---|---:|---:|---:|
| `N11` | `20 / 20` | `20 / 20` | `0` |
| `N12` | `20 / 20` | `20 / 20` | `0` |
| `N13` | `20 / 20` | `19 / 20` | `-1` |

## Criterion Delta

| Scenario | Criterion | X1 | X3 | Delta |
|---|---|---:|---:|---:|
| `N13` | denominator reporting | `4` | `3` | `-1` |

All other criteria tied. The X3 artifact missed the rubric term `route status` in the denominator-reporting criterion; X1 preserved it.

## Interpretation

| Question | Evidence-backed answer |
|---|---|
| Do binary hardened gates rank `X1` and `X3`? | No. Both pass `5 / 5` on `N02`, `S30`, and `N11..N13`. |
| Does E3 add a diagnostic ordering? | Yes, narrowly: `X1 60 / 60` versus `X3 59 / 60`. |
| Is this a strong separator? | No. It is a one-point diagnostic delta, not a binary model-classification split. |
| Should E3 override full-v2 score? | No. It is a diagnostic top-pair quality read only. |

## Machine Output

| Artifact | Role |
|---|---|
| `Evidence/x1-x3-top-pair-rubric-e3-2026-04-20.json` | full machine-readable rubric output |
| `Results-drafts/v2-top-pair-rubric-e3-results-2026-04-20.md` | generated human-readable result surface |
