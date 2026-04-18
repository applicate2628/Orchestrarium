Date: 2026-04-18
Owner: `$lead`
Status: `PASS`

## Result

This is the current compact operator read for the live benchmark state.

The old upgraded-pack tables remain the last full execution checkpoint for `X1..X3`.
`Scenarios-v2` is now execution-backed across the expanded full `S01..S33 + N01..N07` surface for
`X1`, `X2`, `X5`, and `X6`.

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
| `3` | full `Scenarios-v2` `S01..S33 + N01..N07` surface | `gpt-5.4` | `gemini3.1pro` | `gemini3.1flash-lite-preview` | `gpt-spark` |

| `#` | Current rows note | Current state |
|---|---|---|
| `1` | `X1 / gpt-5.4` | admitted on the old full checkpoint and now also strongest on the expanded full v2 surface (`36 / 40`) |
| `2` | `X2 / gpt-spark` | execution-backed across the expanded full v2 surface (`6 / 40`), with many late-surface and usage-limit failures |
| `3` | `X3 / opus 4.7max` | still part of the old full checkpoint; intentionally skipped on the current v2 pass |
| `4` | `X4 / Claude China` | currently parked outside the active comparison surfaces |
| `5` | `X5 / gemini3.1pro` | execution-backed across the expanded full v2 surface (`10 / 40`), but the row hits a strong Gemini quota wall after the early green segment |
| `6` | `X6 / gemini3.1flash-lite-preview` | execution-backed across the expanded full v2 surface (`8 / 40`), admitted from the latest completed fallback full-surface-expanded root after the direct default run stalled |

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | the live v2 surface now includes routing-basis `N01..N07`; compare against the earlier `S01..S33` read only with the surface change in mind | full v2 surface |
| `2` | `X5` current read is heavily quota-entangled from `S12` onward | `gemini3.1pro` |
| `3` | `X6` current read comes from a completed fallback root because the direct default full-surface run stalled after generating only `S01/meta/prompt.txt` | `gemini3.1flash-lite-preview` |
| `4` | `S25` and `S26` were re-audited before this read; tamper checks now fail on metadata drift and protected-surface edits | review-bundle integrity |

## Source

| Source | Role |
|---|---|
| `x1-x3-steady-state-core-results-2026-04-17.md` | old main admitted ranking surface |
| `x1-x3-full-registry-results-2026-04-17.md` | old widest execution-backed registry surface |
| `v2-full-s01-s33-n01-n07-results-2026-04-18.md` | full current expanded v2 result surface |
| `v2-full-s01-s33-results-2026-04-18.md` | earlier same-day `S01..S33` checkpoint, now superseded as the main live v2 read |
| `../Evidence/x1-x2-x5-x6-full-v2-s01-s33-n01-n07-2026-04-18.md` | expanded full-v2 evidence and caveat source |
