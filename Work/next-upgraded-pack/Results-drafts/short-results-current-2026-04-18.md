Date: 2026-04-18
Owner: `$lead`
Status: `PASS`

## Result

This is the current compact operator read for the live benchmark state.

The old upgraded-pack tables remain the last full execution checkpoint for `X1..X3`.
A first bounded `Scenarios-v2` worked-example cohort is now also admitted for `X1`, `X2`, `X5`,
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
| `3` | bounded v2 worked-example cohort | `gpt-5.4` | `gemini3.1pro` | `gemini3.1flash-lite-preview` | `gpt-spark` |

| `#` | Current rows note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | admitted on the old full checkpoint and now also full-green on the bounded v2 worked-example cohort (`7 / 7`) |
| `2` | `X2 / gpt-spark` | admitted on the old full checkpoint, but only `1 / 7` on the first bounded v2 cohort |
| `3` | `X3 / opus 4.7max` | still part of the old full checkpoint; intentionally skipped on the current bounded v2 pass |
| `4` | `X4 / Claude China` | currently parked outside the active comparison surfaces |
| `5` | `X5 / gemini3.1pro` | no longer runtime-blocked on the worked-example v2 slice; bounded v2 read is `5 / 7` |
| `6` | `X6 / gemini3.1flash-lite-preview` | no longer dead on entry; bounded v2 read is `4 / 7`, with runtime and schema caveats |

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | `T29` widening into `src/runToolchainTask.js` on the old upgraded-pack surface | `gpt-spark` |
| `2` | `S32` required a canonical oracle hotfix because the adapter verifier prohibited a snippet that the same contract also required | bounded v2 worked-example cohort |
| `3` | `S32` on `X5` needed manual verifier rerun after the controller timed out post-write | `gemini3.1pro` |
| `4` | `S02` on `X6` passed local verification with a non-zero wrapper exit | `gemini3.1flash-lite-preview` |

## Source

| Source | Role |
|---|---|
| `x1-x3-steady-state-core-results-2026-04-17.md` | old main admitted ranking surface |
| `x1-x3-full-registry-results-2026-04-17.md` | old widest execution-backed registry surface |
| `v2-worked-example-cohort-results-2026-04-18.md` | first admitted bounded v2 result surface |
| `../Evidence/x1-x2-x5-x6-v2-worked-example-cohort-2026-04-18.md` | v2 evidence and caveat source |
