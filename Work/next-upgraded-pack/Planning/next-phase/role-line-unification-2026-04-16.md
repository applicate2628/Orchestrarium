Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file proposes the role-aligned line model for the next upgraded benchmark pack.

The goal is to stop mixing practical role lines with legacy wave rows and test-specific artifacts.

This document follows the upgraded naming rule from `benchmark-taxonomy-and-naming-2026-04-16.md`.

## Proposed role-aligned lines

| Line ID | Proposed line | Primary Orchestrator roles | Merge or absorb current rows | Main test basis |
|---|---|---|---|---|
| `L01` | `research.repo-understanding` | `$analyst` | `Разбор репозитория / source-of-truth` | `T01`, `T02`, `T12` during migration |
| `L02` | `design.architecture-and-planning` | `$architect`, `$planner`, `$product-analyst` | `ADR / архитектура / планирование`, `Product brief / roadmap framing` | `T03`, `T04`, `T02`, `T10`, `T11`, `T13`, `T14` during migration |
| `L03` | `constraints.risk-reasoning` | `$security-engineer`, `$performance-engineer`, `$reliability-engineer` | `Security / perf / reliability / scientist-style` | `T06`, `T07`, `T03`, `T13`, `T14` during migration |
| `L04` | `review.code-and-quality` | `$qa-engineer`, `$architecture-reviewer`, `$security-reviewer`, `$performance-reviewer` | `Pre-PR review / QA / findings-only` | `T05`, `T19`, plus future review probes |
| `L05` | `review.ui-static` | `$accessibility-reviewer`, `$ux-reviewer`, `$ui-test-engineer` | `Accessibility / UX static review`, `Static visual / visualization review`, current static UI evidence row | `T05`, `T18`, `T20` during migration |
| `L06` | `worker.general-implementation` | `$frontend-engineer`, `$backend-engineer`, `$external-worker` | `Реализация фич / багфиксов` | `T08`, `T09`, `T16`, `T17`, `T21` during migration |
| `L07` | `worker.systems-implementation` | `$backend-engineer`, `$platform-engineer`, `$external-worker` | `Systems / performance implementation` | `T08`, `T09`, `T07`, `T15`, `T16`, `T25` during migration |
| `L08` | `worker.toolchain-root-ownership` | `$toolchain-engineer` | `Toolchain / build / project-root ownership` | `T09`, `T10`, `T15`, `T22`, `T25`, `T26` during migration |
| `L09` | `worker.ui-implementation` | `$frontend-engineer`, `$external-worker` | `UI structural modernization`, `UI surgical cleanup`, `Visual / icon decorative edits` | `T08`, `T05`, `T17`, `T20`, `T21`, `T23` during migration |
| `L10` | `worker.long-horizon-autonomy` | assigned worker role, `$external-worker` | `Долгий автономный messy worker-run` | `T10`, `T22`, `T23`, `T24`, `T25`, `T27`, `T28` during migration |

## Surfaces that should become overlays, not role lines

| Overlay ID | Source surface | Proposed future status | Why |
|---|---|---|---|
| `O01` | `W1` | `overlay.provenance-top-path-advisory` | useful historical wave, but not a future practical line name |
| `O02` | `W2` | `overlay.provenance-top-path-risk` | same as above |
| `O03` | `W3` | `overlay.provenance-top-path-worker` | same as above |
| `O04` | `W4` | `overlay.fallback-mechanical` | fallback-only surface, not a general role line |
| `O05` | `W5` | `overlay.fallback-reasoning` | fallback-only surface, not a general role line |
| `O06` | current browser runtime notes | `overlay.browser-runtime` when needed | modality note, not a core role line |

## Current-to-next consolidation read

| Current row | Next place |
|---|---|
| `Разбор репозитория / source-of-truth` | `L01 research.repo-understanding` |
| `ADR / архитектура / планирование` | `L02 design.architecture-and-planning` |
| `Product brief / roadmap framing` | `L02 design.architecture-and-planning` |
| `Security / perf / reliability / scientist-style` | `L03 constraints.risk-reasoning` |
| `Pre-PR review / QA / findings-only` | `L04 review.code-and-quality` |
| `Accessibility / UX static review` | `L05 review.ui-static` |
| `Static visual / visualization review` | `L05 review.ui-static` |
| `Реализация фич / багфиксов` | `L06 worker.general-implementation` |
| `Systems / performance implementation` | `L07 worker.systems-implementation` |
| `Toolchain / build / project-root ownership` | `L08 worker.toolchain-root-ownership` |
| `Долгий автономный messy worker-run` | `L10 worker.long-horizon-autonomy` |
| `UI structural modernization` | `L09 worker.ui-implementation` |
| `UI surgical cleanup` | `L09 worker.ui-implementation` |
| `Visual / icon decorative edits` | `L09 worker.ui-implementation` |
| current standalone static UI evidence row | absorbed into `L05 review.ui-static` as one supporting test, not a separate practical line |

## Why this merge is better

| Benefit | Meaning |
|---|---|
| lines become interpretable through the Orchestrator role model | readers can understand what the row is supposed to represent |
| one line can survive several tests changing over time | lines become more stable than individual probes |
| overlays stop polluting the main ranking surface | fallback or modality notes remain useful without pretending to be role lanes |
| UI becomes cleaner | review-side UI and worker-side UI stop fighting in the same taxonomy |
| naming becomes coherent | `L` lines and `O` overlays are visibly different from atomic `T` tests |

## Steady-state core line basis

This line model now assumes a smaller regular execution surface.
The full registry remains in the migration inventory, but the steady-state core basis is:

| Line | Steady-state core basis |
|---|---|
| `L01` | `T01`, `T12` |
| `L02` | `T03`, `T10` |
| `L03` | `T03`, `T07` |
| `L04` | `T05`, `T19` |
| `L05` | `T05`, `T18`, `T30` |
| `L06` | `T08`, `T09`, `T21` |
| `L07` | `T07`, `T08`, `T09`, `T15`, `T25` |
| `L08` | `T09`, `T10`, `T15`, `T22`, `T25`, `T29` |
| `L09` | `T05`, `T08`, `T21`, `T23`, `T30` |
| `L10` | `T10`, `T22`, `T23`, `T24`, `T25` |

Use the extended pack only when the core leaves a suspicious tie, a rank flip, or a missing confirmation signal.
