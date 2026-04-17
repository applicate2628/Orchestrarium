Date: 2026-04-18
Owner: `$lead`
Status: `PASS`

## Result

This is the first admitted bounded v2 result surface for the worked-example `Scenarios-v2` cohort.
It covers one admitted scenario from each pack `P01..P07` and currently compares `X1`, `X2`, `X5`,
and `X6`. `X3` and `X4` were intentionally skipped on this pass.

| ID | Label |
|---|---|
| `X1` | `gpt-5.4` |
| `X2` | `gpt-spark` |
| `X5` | `gemini3.1pro` |
| `X6` | `gemini3.1flash-lite-preview` |

| `#` | Row | Pass / 7 | Read |
|---|---|---:|---|
| `1` | `X1 / gpt-5.4` | `7 / 7` | best current row on the bounded v2 worked-example cohort |
| `2` | `X5 / gemini3.1pro` | `5 / 7` | clear second on this bounded slice |
| `3` | `X6 / gemini3.1flash-lite-preview` | `4 / 7` | viable but still noisy and inconsistent |
| `4` | `X2 / gpt-spark` | `1 / 7` | weak on this first v2 slice |

## Semantic role table

| `#` | Роль | Сценарий | `X1` | `X5` | `X6` | `X2` |
|---|---|---|---|---|---|---|
| `1` | `R02 $lead` | `S02` | `PASS` | `PASS` | `PASS*` | `FAIL` |
| `2` | `R07 $architect` | `S07` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `3` | `R12 $security-engineer` | `S12` | `PASS` | `FAIL` | `FAIL` | `FAIL` |
| `4` | `R21 $toolchain-engineer` | `S21` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `5` | `R22 $geometry-engineer` | `S22` | `PASS` | `PASS` | `PASS` | `PASS` |
| `6` | `R26 $architecture-reviewer` | `S26` | `PASS` | `FAIL` | `FAIL` | `FAIL` |

## Adapter table

| `#` | Адаптер | Сценарий | `X1` | `X5` | `X6` | `X2` |
|---|---|---|---|---|---|---|
| `1` | `A01 $external-worker` | `S32` | `PASS**` | `PASS***` | `FAIL****` | `FAIL` |

## Notes

| `#` | Note |
|---|---|
| `1` | `*` local verifier passed, but the wrapper exit on `S02` was non-zero for `X6` |
| `2` | `**` `X1` `S32` changed from fail to pass only after correcting the contradictory canonical oracle in `Scenarios-v2/S32-external-worker-transport-fidelity/oracle/provenance-contract.json` |
| `3` | `***` `X5` `S32` produced the right report before the controller timed out; the corrected oracle plus manual verifier rerun admitted it as `PASS` |
| `4` | `****` `X6` `S32` still failed after the oracle hotfix because the report used bulleted labels instead of the exact contract labels |

## Caveats

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | this is a bounded v2 surface only; it does not replace the old upgraded-pack full execution checkpoint | whole table |
| `2` | the `S32` oracle needed a one-line hotfix before adapter scoring was honest | whole table |

## Source

| Source | Role |
|---|---|
| `../Evidence/x1-x2-x5-x6-v2-worked-example-cohort-2026-04-18.md` | admitted evidence and raw-run interpretation |
| `Scenarios-v2/S32-external-worker-transport-fidelity/oracle/provenance-contract.json` | corrected adapter oracle used for the final `S32` read |
