Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Result

This is the current **short compact result table** for the live upgraded-pack surfaces.

The main admitted comparison surface is the steady-state core execution pack for `X1`, `X2`, and `X3`.
The current runnable mutable pack remains a supporting surface.
`X5` and `X6` stay outside the ranked surface as runtime-blocked exploratory rows.

| ID | Label |
|---|---|
| `X1` | `gpt-5.4` |
| `X2` | `gpt-spark` |
| `X3` | `opus 4.7max` |
| `X5` | `gemini3.1pro` |
| `X6` | `gemini3.1flash-lite-preview` |

| `#` | Линия | `1` | `2` | `3` | `4` | `5` |
|---|---|---|---|---|---|---|
| `1` | worker-heavy first batch | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |
| `2` | remaining-core batch | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |
| `3` | steady-state core execution pack | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |
| `4` | extended retrofit batch | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |
| `5` | current runnable mutable pack | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |
| `6` | full execution-backed registry | `gpt-5.4` | `opus 4.7max` | `gpt-spark` |  |  |

| `#` | Линия | Тесты |
|---|---|---|
| `1` | worker-heavy first batch | `T08`, `T09`, `T10`, `T22`, `T23`, `T24`, `T25`, `T29`, `T30` |
| `2` | remaining-core batch | `T01`, `T03`, `T05`, `T07`, `T12`, `T15`, `T18`, `T19`, `T21` |
| `3` | steady-state core execution pack | `T01`, `T03`, `T05`, `T07`, `T08`, `T09`, `T10`, `T12`, `T15` |
|  |  | `T18`, `T19`, `T21`, `T22`, `T23`, `T24`, `T25`, `T29`, `T30` |
| `4` | extended retrofit batch | `T02`, `T04`, `T06`, `T11`, `T13`, `T14`, `T16`, `T17`, `T20` |
| `5` | current runnable mutable pack | `T08`, `T09`, `T10`, `T22`, `T23`, `T24`, `T25`, `T26` |
|  |  | `T27`, `T28`, `T29`, `T30`, `T31`, `T32`, `T33` |
| `6` | full execution-backed registry | `T01`, `T02`, `T03`, `T04`, `T05`, `T06`, `T07`, `T08`, `T09` |
|  |  | `T10`, `T11`, `T12`, `T13`, `T14`, `T15`, `T16`, `T17`, `T18` |
|  |  | `T19`, `T20`, `T21`, `T22`, `T23`, `T24`, `T25`, `T26`, `T27` |
|  |  | `T28`, `T29`, `T30`, `T31`, `T32`, `T33` |

| `#` | Current rows note | Current state |
|---|---|---|
| `1` | `X1` / `gpt-5.4` | admitted on full steady-state core surface and now also execution-backed across the full `T01..T33` registry |
| `2` | `X2` / `gpt-spark` | admitted on full steady-state core surface and full registry, but with `T29` toolchain-discipline caveat |
| `3` | `X3` / `opus 4.7max` | admitted on full steady-state core surface and now also execution-backed across the full `T01..T33` registry |
| `4` | `X4` / `Claude China` | currently parked outside the active upgraded-pack comparison surface |
| `5` | `X5` / `gemini3.1pro` | exploratory retry only, runtime-blocked |
| `6` | `X6` / `gemini3.1flash-lite-preview` | exploratory retry only, runtime-blocked |

| `#` | Caveat | Applies to |
|---|---|---|
| `1` | `T29` widening into `src/runToolchainTask.js` | `gpt-spark` |

## Source

| Source | Role |
|---|---|
| `x1-x3-steady-state-core-results-2026-04-17.md` | main admitted ranking surface |
| `x1-x3-full-registry-results-2026-04-17.md` | widest execution-backed registry surface |
| `x1-x3-current-runnable-pack-results-2026-04-17.md` | supporting worker-heavy runnable surface |
| `../Evidence/x5-worker-heavy-triage-2026-04-17.md` | `X5` runtime-blocked exploratory note |
| `../Evidence/x6-worker-heavy-retry-2026-04-17.md` | `X6` runtime-blocked exploratory note |
