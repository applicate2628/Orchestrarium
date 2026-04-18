Date: 2026-04-18
Owner: `$lead`
Status: `PASS`

## Result

This is the current compact operator read for the live benchmark state.

The old upgraded-pack tables remain the last full execution checkpoint for `X1..X3`.
`Scenarios-v2` is now execution-backed across the full `S01..S33` surface for `X1`, `X2`, `X5`,
and `X6`.

| ID | Label |
|---|---|
| `X1` | `gpt-5.4` |
| `X2` | `gpt-spark` |
| `X3` | `opus 4.7max` |
| `X5` | `gemini3.1pro` |
| `X6` | `gemini3.1flash-lite-preview` |

| `#` | Surface | `1` | `2` | `3` | `4` |
|---|---|---|---|---|---|
| `1` | steady-state core execution pack | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |
| `2` | full execution-backed upgraded-pack registry | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |
| `3` | full `Scenarios-v2` `S01..S33` surface | `gpt-5.4` | `gemini3.1pro` | `gpt-spark` | `gemini3.1flash-lite-preview` |

| `#` | Current rows note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | admitted on the old full checkpoint and now also strongest on full v2 (`31 / 33`) |
| `2` | `X2 / gpt-spark` | admitted on the old full checkpoint and now execution-backed across full v2 (`14 / 33`) |
| `3` | `X3 / opus 4.7max` | still part of the old full checkpoint; intentionally skipped on the current v2 pass |
| `4` | `X4 / Claude China` | currently parked outside the active comparison surfaces |
| `5` | `X5 / gemini3.1pro` | execution-backed across full v2 (`27 / 33`), with one manual `S32` verifier rerun and a failed `S33` |
| `6` | `X6 / gemini3.1flash-lite-preview` | execution-backed across full v2 (`12 / 33`), but heavily fragmented by quota/tool noise |

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | `T29` widening into `src/runToolchainTask.js` on the old upgraded-pack surface | `gpt-spark` |
| `2` | `S32` required a canonical oracle hotfix because the adapter verifier prohibited a snippet that the same contract also required | full v2 surface |
| `3` | `S32` on `X5` is admitted from the produced report plus manual completed-verifier rerun because the controller never emitted `summary.json` | `gemini3.1pro` |
| `4` | several `X6` passes still carry wrapper exit `1`, and many `X6` failures are entangled with Gemini tool/quota noise | `gemini3.1flash-lite-preview` |

## Source

| Source | Role |
|---|---|
| `x1-x3-steady-state-core-results-2026-04-17.md` | old main admitted ranking surface |
| `x1-x3-full-registry-results-2026-04-17.md` | old widest execution-backed registry surface |
| `v2-full-s01-s33-results-2026-04-18.md` | full current v2 result surface |
| `v2-worked-example-cohort-results-2026-04-18.md` | earlier bounded v2 checkpoint |
| `../Evidence/x1-x2-x5-x6-full-v2-s01-s33-2026-04-18.md` | full-v2 evidence and caveat source |
