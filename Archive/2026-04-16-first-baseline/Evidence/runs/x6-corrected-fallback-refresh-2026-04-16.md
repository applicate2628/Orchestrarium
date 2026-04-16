Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

Close the remaining exact-target cleanup debt for `X6` by refreshing the current Gemini fallback path under:

- `gemini-3.1-flash-lite-preview`

This artifact covers the two previously stale layers:

- non-browser role-gap rows `G01..G07`, `G09`, `G10`
- exact-target model-only rows `M01..M10`

The strict browser row `G08` is intentionally **not** part of this refresh. It remains a separate current-fail browser note.

## Execution surface

| Scope | Target | Concrete model / path | Output root |
|---|---|---|---|
| role-gap refresh | `X6` | `gemini-3.1-flash-lite-preview` | `.scratch/x6-refresh-2026-04-16/G-correct/` |
| exact-target refresh | `X6` | `gemini-3.1-flash-lite-preview` | `.scratch/x6-refresh-2026-04-16/M/` |

## Role-gap refresh verdicts

| Probe | Verdict | Basis |
|---|---|---|
| `G01` | `PASS` | output stayed inside the ranked-list contract and grounded the milestone choice correctly |
| `G02` | `PASS` | product brief response stayed inside the requested structure and blocker framing |
| `G03` | `PASS` | reliability response stayed inside the failure-mode / mitigation contract |
| `G04` | `PASS` | scientist-style proof and invariant framing stayed inside the requested formal structure |
| `G05` | `PASS` | toolchain diagnosis response stayed inside the root-cause and next-check contract |
| `G06` | `PASS` | backend/data role-gap memo stayed inside the requested asset and ownership framing |
| `G07` | `PASS` | platform / architecture findings stayed inside the structural review contract |
| `G09` | `PASS` | a11y / UX findings response stayed inside the findings-only contract |
| `G10` | `PASS` | browser-free visual review memo stayed inside the requested defect-description contract |

## Exact-target refresh verdicts

| Probe | Verdict | Basis |
|---|---|---|
| `M01` | `PASS` | factual extraction stayed exact and bounded |
| `M02` | `PASS` | canonical-source conflict reconciliation stayed admissible |
| `M03` | `PASS` | ADR memo stayed inside the required section contract |
| `M04` | `PASS` | phased plan stayed inside the required phase structure |
| `M05` | `PASS` | findings-only review returned concrete bounded findings again under the corrected fallback |
| `M06` | `PASS` | security memo stayed threat-aware and contract-bounded |
| `M07` | `PASS` | performance memo stayed measurable and bounded |
| `M08` | `PASS with deviation` | model landed the right minimal code change, but could not self-run shell verification; host-side `node --test` confirmed the fix |
| `M09` | `PASS` | root-cause memo again identified the real `provider_local_note` leak |
| `M10` | `PASS` | resume and stale-context handling stayed admissible |

## M08 deviation note

| Field | Accepted read |
|---|---|
| model behavior | `X6` removed the leaking `provider_local_note` push and named the correct minimal fix in `src/mergeLaneVerdict.js` |
| runtime limitation | current local Gemini tool surface blocked `run_shell_command`, so the answer claimed analysis-only verification |
| host-side verification | the workspace at `.scratch/gemini-exact-reruns-2026-04-14/x6/work/M08/` passes `node --test` after the applied patch |
| benchmark verdict | admit as `PASS with deviation`, not as a fully self-verified no-caveat row |

## High-signal findings

| Topic | Accepted finding |
|---|---|
| corrected fallback closure | `X6` no longer has any open non-browser cleanup debt on `G01..G10` or `M01..M10` under the current fallback label `gemini-3.1-flash-lite-preview` |
| old exact-target alias | earlier `gemini-3-flash-high-explicit` rows remain historical provenance only; they are no longer the active exact-target surface |
| review and reasoning coverage | the old historical `2.5-flash` fallback picture is now fully superseded on the non-browser model-only slice |
| browser boundary | this refresh does **not** change the current strict `G08` browser fail note for `X6`; browser parity remains a separate current restriction |

## Raw output pointers

| Scope | Files |
|---|---|
| `G` refresh | `.scratch/x6-refresh-2026-04-16/G-correct/G01.json.txt`, `G02.json.txt`, `G03.json.txt`, `G04.json.txt`, `G05.json.txt` |
|  | `.scratch/x6-refresh-2026-04-16/G-correct/G06.json.txt`, `G07.json.txt`, `G09.json.txt`, `G10.json.txt` |
| `M` refresh | `.scratch/x6-refresh-2026-04-16/M/M01.json.txt`, `M02.json.txt`, `M03.json.txt`, `M04.json.txt`, `M05.json.txt` |
|  | `.scratch/x6-refresh-2026-04-16/M/M06.json.txt`, `M07.json.txt`, `M08-clean.txt`, `M09-correct.txt`, `M10.json.txt` |

