Date: 2026-04-21
Owner: `$lead`
Status: `PASS`

## Scope

This evidence records the current `X1` / `X5` complexity read while `X3` is quota-blocked and must
not be invoked.

`X3` was not run in this pass.

## Results

| Surface | Scenario(s) | `X1 / gpt-5.4` | `X5 / gemini3.1pro` | Read |
|---|---|---|---|---|
| hardened mainline separator set | `N11`, `N12`, `N13`, `S29` | already `PASS` on all latest hardened runs | `4 / 4 PASS` | too easy for `X1` vs `X5` |
| current UX review gate | `S30` | `PASS` | `FAIL` | useful medium separator |
| interaction-state flow hardening | `N02` source-trace only | `PASS` | `PASS` | improved contract but still too easy |
| interaction-state flow hardening | `N02` trace-table requirement | `PASS` | `FAIL` | useful separator |

## Run Roots

| Row | Scenario(s) | Root |
|---|---|---|
| `X5` | `N11`, `N12`, `N13`, `S29` | `.scratch/v2-cohort-runs/2026-04-21_01-25-39-X5-x5-mainline-hardening-complexity-check-2026-04-21/` |
| `X1` | `S30` | `.scratch/v2-cohort-runs/2026-04-21_01-40-05-X1-x1-s30-current-complexity-check-2026-04-21/` |
| `X5` | `S30` | `.scratch/v2-cohort-runs/2026-04-21_01-40-05-X5-x5-s30-current-complexity-check-2026-04-21/` |
| `X1` | `N02` source-trace only | `.scratch/v2-cohort-runs/2026-04-21_01-52-10-X1-x1-n02-source-trace-hardening-2026-04-21/` |
| `X5` | `N02` source-trace only | `.scratch/v2-cohort-runs/2026-04-21_01-52-10-X5-x5-n02-source-trace-hardening-2026-04-21/` |
| `X1` | `N02` trace-table requirement | `.scratch/v2-cohort-runs/2026-04-21_01-57-06-X1-x1-n02-trace-table-hardening-2026-04-21/` |
| `X5` | `N02` trace-table requirement | `.scratch/v2-cohort-runs/2026-04-21_01-57-06-X5-x5-n02-trace-table-hardening-2026-04-21/` |

## X5 S30 Failure

`X5/S30` is a scoreable verifier failure:

| Field | Value |
|---|---|
| wrapper exit | `0` |
| verifier | `check_ux_review.py=1` |
| changed paths | `candidate/review-report.md` |
| failure class | output-contract / role-fidelity failure |

Verifier diagnostics:

| Missing requirement | Evidence |
|---|---|
| `## Findings` section | verifier log: `ERROR: Missing report section: ## Findings` |
| `## False Positives Avoided` section | verifier log: `ERROR: Missing report section: ## False Positives Avoided` |

The generated report did identify the three expected UX issues, but used non-contract sections
(`## High Severity`, `## Medium Severity`) and omitted the false-positive discipline section.

## X5 N02 Trace-Table Failure

`X5/N02` is a scoreable verifier failure after the trace-table hardening:

| Field | Value |
|---|---|
| wrapper exit | `0` |
| verifier | `check_interaction_state_flow_brief.py=1` |
| changed paths | `candidate/ux-structure-brief.md` |
| failure class | source-trace completeness / role-fidelity failure |

Verifier diagnostics include missing boundary discipline and missing required source-trace terms:

| Missing requirement | Evidence |
|---|---|
| implementation boundary | verifier log: missing `implementation stays out of scope` / equivalent |
| review boundary | verifier log: missing `review findings stay out of scope` / equivalent |
| source trace specificity | verifier log: missing `web review acknowledged`, `resume from here`, `publish approval`, `same loop` |
| flow specificity | verifier log: missing `returned`, `ready to re-enter` |
| resume cue specificity | verifier log: missing `resume target`, `visible cue`, `what changed`, `where the operator left` |

The generated report did add the required trace tables, but the trace stayed too generic and did not
preserve the admitted source-language and boundary constraints.

## Complexity Read

| Question | Answer |
|---|---|
| Can current hardened `N11/N12/N13/S29` separate `X1` from `X5`? | No. `X5` passed all four. |
| Can current `S30` separate `X1` from `X5`? | Yes. `X1` passed and `X5` failed verifier. |
| Can hardened `N02` separate `X1` from `X5`? | Yes, after requiring structured source-to-state trace tables. |
| Is the `X5/S30` failure quota or timeout? | No. It is scoreable: wrapper exit `0`, candidate changed, verifier failed. |
| Is the `X5/N02` trace-table failure quota or timeout? | No. It is scoreable: wrapper exit `0`, candidate changed, verifier failed. |
| What does this imply for next hardening? | Use structured source-trace requirements and `S30`-style output-contract discipline as the minimum useful complexity floor; `N11/N12/N13/S29` keyword-only tightening is not hard enough for `X1`/`X5`. |
