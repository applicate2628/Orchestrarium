Date: 2026-04-18
Owner: `$lead`
Status: `PASS`

## Scope

This file admits the first bounded v2 provider rerun against the worked-example `Scenarios-v2`
cohort. The slice covers one admitted scenario from each pack `P01..P07`.

| Item | Value |
|---|---|
| rows in scope | `X1`, `X2`, `X5`, `X6` |
| skipped by current instruction | `X3`, `X4` |
| scenario set | `S02`, `S07`, `S12`, `S21`, `S22`, `S26`, `S32` |
| pack coverage | `P01`, `P02`, `P03`, `P04`, `P05`, `P06`, `P07` |
| runner surface | `Tooling/run-v2-cohort-batch.ps1` |

## Raw execution roots

| Row | Scenario | Raw scratch root |
|---|---|---|
| `X1` | full worked-example pack | `.scratch/v2-cohort-runs/2026-04-17_23-46-55-X1-v2-worked-example-pack/` |
| `X2` | full worked-example pack | `.scratch/v2-cohort-runs/2026-04-17_23-46-55-X2-v2-worked-example-pack/` |
| `X5` | `S02` | `.scratch/v2-cohort-runs/2026-04-17_22-52-46-X5-x5-s02-pwsh/` |
|  | `S07` | `.scratch/v2-cohort-runs/2026-04-17_22-57-10-X5-x5-s07-pwsh/` |
|  | `S12` | `.scratch/v2-cohort-runs/2026-04-17_22-59-14-X5-x5-s12-pwsh/` |
|  | `S21` | `.scratch/v2-cohort-runs/2026-04-17_23-02-27-X5-x5-s21-pwsh/` |
|  | `S22` | `.scratch/v2-cohort-runs/2026-04-17_23-05-08-X5-x5-s22-pwsh/` |
|  | `S26` | `.scratch/v2-cohort-runs/2026-04-17_23-13-53-X5-x5-s26-pwsh/` |
|  | `S32` rerun | `.scratch/v2-cohort-runs/2026-04-18_00-24-53-X5-x5-s32-rerun-pwsh/` |
| `X6` | `S02` | `.scratch/v2-cohort-runs/2026-04-18_00-11-05-X6-x6-s02-pwsh/` |
|  | `S07` | `.scratch/v2-cohort-runs/2026-04-18_00-12-52-X6-x6-s07-pwsh/` |
|  | `S12` | `.scratch/v2-cohort-runs/2026-04-18_00-15-05-X6-x6-s12-pwsh/` |
|  | `S21` | `.scratch/v2-cohort-runs/2026-04-18_00-17-14-X6-x6-s21-pwsh/` |
|  | `S22` | `.scratch/v2-cohort-runs/2026-04-18_00-18-47-X6-x6-s22-pwsh/` |
|  | `S26` | `.scratch/v2-cohort-runs/2026-04-18_00-21-03-X6-x6-s26-pwsh/` |
|  | `S32` rerun | `.scratch/v2-cohort-runs/2026-04-18_00-24-53-X6-x6-s32-rerun-pwsh/` |

## Scenario read

| Scenario | Surface | `X1` | `X5` | `X6` | `X2` | Notes |
|---|---|---|---|---|---|---|
| `S02` | `R02 $lead` | `PASS` | `PASS` | `PASS*` | `FAIL` | `X6` local verifier passed even though wrapper exit was non-zero |
| `S07` | `R07 $architect` | `PASS` | `PASS` | `PASS` | `FAIL` |  |
| `S12` | `R12 $security-engineer` | `PASS` | `FAIL` | `FAIL` | `FAIL` |  |
| `S21` | `R21 $toolchain-engineer` | `PASS` | `PASS` | `PASS` | `FAIL` |  |
| `S22` | `R22 $geometry-engineer` | `PASS` | `PASS` | `PASS` | `PASS` |  |
| `S26` | `R26 $architecture-reviewer` | `PASS` | `FAIL` | `FAIL` | `FAIL` |  |
| `S32` | `A01 $external-worker` | `PASS**` | `PASS***` | `FAIL****` | `FAIL` | adapter-only transport surface |

## Row summary

| Row | Label | Pass count | Read |
|---|---|---:|---|
| `X1` | `gpt-5.4` | `7 / 7` | full green on the bounded v2 worked-example cohort after the `S32` oracle correction |
| `X5` | `gemini3.1pro` | `5 / 7` | now execution-backed on the bounded v2 slice; misses remain on `S12` and `S26` |
| `X6` | `gemini3.1flash-lite-preview` | `4 / 7` | no longer dead on entry, but still loses `S12`, `S26`, and `S32` |
| `X2` | `gpt-spark` | `1 / 7` | only `S22` passed on this first v2 slice |

## `S32` contract correction

While consolidating the cohort, I found a verifier contradiction in the canonical `S32` oracle:
the scenario required the exact scope sentence `No internal specialist, reviewer, or consultant
fallback was used.` and also prohibited the substring `consultant fallback`. That made a correct
completed report fail by construction.

| Path | Change | Reason |
|---|---|---|
| `Scenarios-v2/S32-external-worker-transport-fidelity/oracle/provenance-contract.json` | removed prohibited snippet `consultant fallback` | the snippet directly conflicted with the required scope sentence and invalidated otherwise correct reports |

After the correction:

| Row | Verification read on corrected `S32` oracle |
|---|---|
| `X1` | `python verifiers/check_transport_report.py --mode completed` -> `PASS` |
| `X5` | `python verifiers/check_transport_report.py --mode completed` -> `PASS` |
| `X6` | same command still `FAIL` because the report used bulleted label lines instead of the exact required label format |
| `X2` | same command `FAIL` because the candidate stayed at the seeded placeholder state |

## Caveat notes

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | local verifier passed but wrapper exit was non-zero on `S02` | `X6` |
| `2` | `S32` controller timed out after the report was already written; final read used the produced report plus manual verifier rerun on the corrected oracle | `X5` |
| `3` | `S32` failed for real schema-discipline reasons after the oracle hotfix; the report kept Markdown bullets where the contract requires exact label lines | `X6` |

## Verdict

`PASS` - the first bounded v2 rerun is now execution-backed for `X1`, `X2`, `X5`, and `X6` on the
worked-example pack. The surface is strong enough to admit `X5` and `X6` into v2 evidence, but it
is still a bounded cohort and does not replace the old upgraded-pack full-checkpoint tables.

The next honest step is to widen the v2 cohort beyond the worked-example pack, or to bring `X3`
and `X4` back in if the current user instruction changes.
