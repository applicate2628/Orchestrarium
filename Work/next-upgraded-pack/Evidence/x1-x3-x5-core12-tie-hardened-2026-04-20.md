Date: 2026-04-20
Owner: `$lead`
Status: `PASS`

## Scope

This evidence covers the hardened weak-separator subset for `X1`, `X3`, and `X5`.

It is a targeted tiebreaker over the previously tied core-12 lanes, not a replacement for the
full `S01..S33 + N01..N07` score. The hardened subset uses the same scenario IDs but stricter
contracts/verifiers for the tied lanes:

| Lane | Basis |
|---|---|
| `advisory.repo-understanding` | `S03`, `S04`, `S06` |
| `advisory.design-adr` | `S05`, `S07`, `S09` |
| `design.ui-ux-structure` | `S08`, `N01`, `N02` |
| `review.pre-pr` | `S25`, `N03`, `N04` |
| `review.security` | `S27`, `N05`, `N06` |

Quota, provider-limit, and runtime timeout cells are not scored as verifier `FAIL`.

## Run Roots

| Row | Root |
|---|---|
| `X1` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_02-31-18-X1-x1-core12-tie-hardened-2026-04-20/` |
| `X3` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_03-15-46-X3-x3-core12-tie-hardened-2026-04-20/` |
| `X5` first attempt | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_02-31-18-X5-x5-core12-tie-hardened-2026-04-20/` |
| `X5` quota requeue | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_03-22-01-X5-x5-core12-tie-hardened-requeue-2026-04-20/` |
| `X5` `N03` retry | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_05-18-03-X5-x5-core12-tie-hardened-requeue-n03-n06-2026-04-20/` |
| `X5` `N04` retry | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_06-50-06-X5-x5-core12-hardened-direct-n04-2026-04-20/` |
| `X5` `N05` retry | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_07-21-33-X5-x5-core12-hardened-direct-n05-2026-04-20/` |
| `X5` `N06` retry | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_07-34-20-X5-x5-core12-hardened-direct-n06-2026-04-20/` |
| `X5` timeout closure `N02/N03` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_18-28-31-X5-x5-core12-hardened-close-timeouts-n02-n06-2026-04-20/` |
| `X5` timeout closure `N04` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_19-32-07-X5-x5-core12-hardened-close-timeout-n04-2026-04-20b/` |
| `X5` timeout closure `N05` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_20-03-05-X5-x5-core12-hardened-close-timeout-n05-2026-04-20b/` |
| `X5` timeout closure `N06` | `benchmarks/.scratch/v2-cohort-runs/2026-04-20_20-34-09-X5-x5-core12-hardened-close-timeout-n06-2026-04-20b/` |

## Result Matrix

| Scenario | X1 `gpt-5.4` | X3 `opus 4.7max` | X5 `gemini3.1pro` |
|---|---|---|---|
| `S03` | `PASS` | `PASS` | `PASS` |
| `S04` | `PASS` | `PASS` | `PASS` |
| `S05` | `PASS` | `PASS` | `PASS` |
| `S06` | `PASS` | `PASS` | `PASS` |
| `S07` | `PASS` | `PASS` | `PASS` after quota requeue |
| `S08` | `PASS` | `PASS` | `PASS` after quota requeue |
| `S09` | `PASS` | `PASS` | `PASS` after quota requeue |
| `S25` | `PASS` | `PASS` | `FAIL` |
| `S27` | `PASS` | `PASS` | `PASS` after quota requeue |
| `N01` | `PASS` | `PASS` | `PASS` after quota requeue |
| `N02` | `PASS` | `PASS` | `PASS` after timeout closure |
| `N03` | `PASS` | `PASS` | `FAIL` after timeout closure |
| `N04` | `PASS` | `PASS` | `PASS` after isolated direct-prompt timeout closure |
| `N05` | `PASS` | `PASS` | `FAIL` after isolated direct-prompt timeout closure |
| `N06` | `PASS` | `PASS` | `PASS` after timeout closure |

## Scoreable Read

| Row | Admitted scoreable PASS | Admitted scoreable FAIL | Timeout / incomplete | Read |
|---|---:|---:|---:|---|
| `X1 / gpt-5.4` | `15` | `0` | `0` | clean sweep on hardened subset |
| `X3 / opus 4.7max` | `15` | `0` | `0` | clean sweep on hardened subset |
| `X5 / gemini3.1pro` | `12` | `3` | `0` | weaker on hardened review/security tail; former timeout cells have scoreable closure states |

## Lane Read

| Lane | X1 | X3 | X5 |
|---|---|---|---|
| `advisory.repo-understanding` | `3 / 3 PASS` | `3 / 3 PASS` | `3 / 3 PASS` |
| `advisory.design-adr` | `3 / 3 PASS` | `3 / 3 PASS` | `3 / 3 PASS` |
| `design.ui-ux-structure` | `3 / 3 PASS` | `3 / 3 PASS` | `3 / 3 PASS` |
| `review.pre-pr` | `3 / 3 PASS` | `3 / 3 PASS` | `1 PASS`, `2 FAIL` |
| `review.security` | `3 / 3 PASS` | `3 / 3 PASS` | `2 PASS`, `1 FAIL` |

## X5 Runtime And Failure Notes

| Scenario | Evidence | Classification |
|---|---|---|
| `S07..N06` first attempt | worker output contains `TerminalQuotaError: You have exhausted your capacity on this model.` with `reason: 'QUOTA_EXHAUSTED'` | `REQUEUE`, not `FAIL` |
| `S25` | `S25/meta/verify-python-check-qa-verdict-py.txt` | real verifier `FAIL`: missing `nearby smoke` in `## Residual Risk` |
| `N02` | normal runner closure wrote `summary.json`; verifier passed `candidate/ux-structure-brief.md` | scoreable `PASS` |
| `N03` | normal runner closure wrote `summary.json`; verifier failed on required finding order | scoreable `FAIL` |
| `N04` | stdin transport hung twice; isolated direct-prompt transport returned `exit=0`, then verifier passed `candidate/regression-triage-report.md` | scoreable `PASS` via direct-prompt closure |
| `N05` | stdin transport hung; isolated direct-prompt transport returned `exit=0`, then verifier failed missing required secret-exposure anchors and false-positive boundaries | scoreable `FAIL` via direct-prompt closure |
| `N06` | normal runner closure wrote `summary.json`; verifier passed `candidate/review-report.md` | scoreable `PASS` |

## Timeout Closure Note

`N04` and `N05` required a transport workaround: the same Gemini model, isolated temporary HOME, and
no MCP were used, but the prompt was passed as `--prompt <text>` instead of the archived wrapper's
`--prompt=` plus stdin transport. No scenario files or verifier files were changed.

## Invalid / Excluded Attempt

| Root | Reason |
|---|---|
| `benchmarks/.scratch/v2-cohort-runs/2026-04-20_06-49-21-X5-x5-core12-hardened-single-n04-2026-04-20/` | excluded infrastructure attempt; custom `Start-Process` wrapper launched a child environment where `Get-FileHash` was unavailable before model execution |
