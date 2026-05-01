Date: 2026-05-01
Owner: `$knowledge-archivist`
Status: `RUN / BINARY TIE`

## Purpose

This map embeds the pre-v3 RF12 line read used to seed a clean Scenarios-v3 starting point.

## Source Basis

| Surface | Path |
|---|---|
| line registry | `../../../Scenarios-v3/_registry/scenarios-v3-base.json` |
| distilled result read | embedded in this file; raw pre-v3 run outputs are not copied forward |
| root policy | no Scenarios-v2 roots are copied forward until redesigned and admitted as v3 |

## Migration Matrix

| Line | S2 slots | S2 read | V3 disposition |
|---|---|---|---|
| `L00 owner/control` | `N17,N67,N40,N56` | split | keep as routing anchor; do not retest first |
| `L01 advisory.repo-understanding` | `S03,S04,S06` | near-tie | low-priority unless a new source-binding separator is designed |
| `L02 advisory.design-adr` | `S05,S07,S09` | near-tie | `V3L02` run completed; `binary tie remains` for `X1` vs `X3` |
| `L03 design.ui-ux-structure` | `S08,N01,N02` | split by trigger | keep trigger policy; staged UX reentry already routes X1 after `N126` |
| `L04 worker.reasoning-constraints` | `N22,N32,N58` | split | possible second wave if scientific/runtime split needs stronger proof |
| `L05 worker.default-implementation` | `N35,N36,N57` | split | keep as anchor for staged vs compact implementation |
| `L06 systems/performance-worker` | `N19,N39,N85` | split | keep as anchor for staged systems vs compact perf hot path |
| `L07 worker.ui-implementation` | `N25,N47,N60` | `X3` | keep as compact UI anchor; staged UI may become future wave |
| `L08 worker.visual/graphics` | `S22,N110,N48` | `X3` | keep pixel-localization and compact visual patch patterns |
| `L09 review.pre-pr` | `S25,N03,N04` | near-tie | keep tuple-exact tie; budgeted review uses RF12 overlay |
| `L10 review.security` | `S27,N05,N06` | near-tie | keep tuple-exact tie; compact budgeted security remains overlay |
| `L11 review.performance-architecture` | `S28,N07,N37` | `X1` | keep staged source-bound review anchor |
| `L12 review.ui-visual-correctness` | `N80,N98,N105` | `X1` | keep calibrated screenshot and visual diff review anchor |

## First Candidate

| Field | Value |
|---|---|
| proposed root | `V3L02-adr-long-horizon-source-conflict` |
| target line | `L02 advisory.design-adr` |
| target separation | ordinary/source-ranked ADR, not staged-review or output-budget-only |
| expected hardening | conflicting source freshness, downstream compatibility, rollback, rejected options, non-claim ledger, exact decision tuple |
| status | run completed; `X1 PASS`, `X3 PASS`, `X2 scoreable FAIL calibration`, `X4 NOT-RUN disabled` |

## Terms and Abbreviations

- `ADR`: Architecture Decision Record.
- `RF12`: role-fit scorecard over twelve routing lines plus one owner/control line.
- `S2`: pre-v3 scenario generation used only as a distilled line-basis label here.
- `V3`: Scenarios-v3 benchmark generation.
