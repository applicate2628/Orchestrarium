Date: 2026-04-18
Owner: `$lead`
Status: `PASS`
Classification status: `DEPRECATED / SUPERSEDED`

## Result

This is the first admitted full-v2 result surface covering `S01..S33` for `X1`, `X2`, `X5`, and
`X6`.

This file is retained only as historical pre-v3 execution evidence. It was superseded first by
`v2-full-s01-s33-n01-n07-results-2026-04-18.md` and is now superseded for current classification by
`full-v2-hard-results-current.md`.

| ID | Label |
|---|---|
| `X1` | `gpt-5.4` |
| `X2` | `gpt-spark` |
| `X5` | `gemini3.1pro` |
| `X6` | `gemini3.1flash-lite-preview` |

| `#` | Row | Pass / 33 | Read |
|---|---|---:|---|
| `1` | `X1 / gpt-5.4` | `31 / 33` | strongest row on this deprecated historical checkpoint |
| `2` | `X5 / gemini3.1pro` | `27 / 33` | clear second on this deprecated historical checkpoint |
| `3` | `X2 / gpt-spark` | `14 / 33` | mixed row; stronger on some document and review surfaces than on the harder reasoning and implementation slices |
| `4` | `X6 / gemini3.1flash-lite-preview` | `12 / 33` | coverage-complete but noisy, quota-sensitive, and unstable |

## Full table

| `#` | Scenario | `X1` | `X5` | `X2` | `X6` |
|---|---|---|---|---|---|
| `1` | `S01` | `PASS` | `PASS` | `PASS` | `PASS*` |
| `2` | `S02` | `PASS` | `PASS` | `FAIL` | `PASS*` |
| `3` | `S03` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `4` | `S04` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `5` | `S05` | `PASS` | `PASS` | `PASS` | `PASS*` |
| `6` | `S06` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `7` | `S07` | `PASS` | `PASS` | `FAIL` | `PASS` |
| `8` | `S08` | `PASS` | `PASS` | `FAIL` | `FAIL` |
| `9` | `S09` | `FAIL` | `PASS` | `FAIL` | `FAIL` |
| `10` | `S10` | `PASS` | `FAIL` | `FAIL` | `FAIL` |
| `11` | `S11` | `FAIL` | `PASS` | `FAIL` | `FAIL` |
| `12` | `S12` | `PASS` | `FAIL` | `FAIL` | `FAIL` |
| `13` | `S13` | `PASS` | `PASS` | `FAIL` | `FAIL` |
| `14` | `S14` | `PASS` | `FAIL` | `FAIL` | `FAIL` |
| `15` | `S15` | `PASS` | `PASS` | `FAIL` | `PASS` |
| `16` | `S16` | `PASS` | `FAIL` | `PASS` | `FAIL` |
| `17` | `S17` | `PASS` | `PASS` | `FAIL` | `PASS` |
| `18` | `S18` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `19` | `S19` | `PASS` | `PASS` | `FAIL` | `PASS` |
| `20` | `S20` | `PASS` | `PASS` | `FAIL` | `FAIL` |
| `21` | `S21` | `PASS` | `PASS` | `FAIL` | `PASS` |
| `22` | `S22` | `PASS` | `PASS` | `PASS` | `PASS` |
| `23` | `S23` | `PASS` | `PASS` | `PASS` | `PASS` |
| `24` | `S24` | `PASS` | `PASS` | `FAIL` | `PASS` |
| `25` | `S25` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `26` | `S26` | `PASS` | `FAIL` | `FAIL` | `FAIL` |
| `27` | `S27` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `28` | `S28` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `29` | `S29` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `30` | `S30` | `PASS` | `PASS` | `FAIL` | `PASS` |
| `31` | `S31` | `PASS` | `PASS` | `PASS` | `FAIL` |
| `32` | `S32` | `PASS**` | `PASS***` | `FAIL` | `FAIL` |
| `33` | `S33` | `PASS` | `FAIL` | `FAIL` | `FAIL` |

## Notes

| `#` | Note |
|---|---|
| `1` | `*` wrapper exit was non-zero, but local verification passed |
| `2` | `**` `X1` `S32` is admitted green on the corrected oracle even though the original `summary.json` still reflects the pre-hotfix failure |
| `3` | `***` `X5` `S32` is admitted green from the produced report plus manual completed-verifier rerun on the corrected oracle; the controller never emitted `summary.json` |

## Caveats

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | `X5` and especially `X6` required fragmented reruns after remaining-pack batch instability | `gemini3.1pro`, `gemini3.1flash-lite-preview` |
| `2` | `X6` full coverage should not be mistaken for runtime cleanliness; many scenarios completed with quota and tool-noise around the verifier path | `gemini3.1flash-lite-preview` |
| `3` | `S32` uses the corrected adapter oracle, not the earlier contradictory version | whole table |

## Source

| Source | Role |
|---|---|
| `../Evidence/x1-x2-x5-x6-full-v2-s01-s33-2026-04-18.md` | admitted evidence and caveat source |
| `v2-worked-example-cohort-results-2026-04-18.md` | earlier bounded-v2 checkpoint, now superseded as the main v2 result surface |
| `v2-full-s01-s33-n01-n07-results-2026-04-18.md` | expanded pre-v3 baseline that superseded this file before `full-v2-hard-results-current.md` became the canonical hardened `/40` surface |
