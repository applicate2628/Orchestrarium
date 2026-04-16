Date: 2026-04-17
Owner: `$lead`
Status: `PASS`

## Purpose

This file defines the steady-state execution surface for the upgraded benchmark pack.

The registry stays full at `T01..T33`, but regular execution should become smaller and more stable.

## Execution-surface rule

| Surface | Meaning |
|---|---|
| full registry | complete benchmark inventory for provenance, migration, and later extension |
| core execution pack | smaller steady-state pack used for routine ranking and most reruns |
| extended pack | confirmation and tie-break tests that are not needed in every regular run |
| incubation | designed or emerging tests that are not part of steady-state execution yet |

## Size target

| Surface | Target size | Current read |
|---|---:|---|
| full registry | `33` | keep complete |
| steady-state core execution pack | `18 +/- 2` | target `18` now |
| extended pack | flexible | remaining hardened non-core tests |
| incubation | flexible | tests not yet admitted into regular execution |

## Core-pack selection principles

| Rule | Meaning |
|---|---|
| keep one or two anchors per non-worker line | advisory, design, review, and static UI lines should stay interpretable without redundant near-duplicates |
| keep multiple pressures on worker lines | implementation, toolchain, and long-horizon worker lines need more than one strong test |
| prefer stronger upgraded probes over weaker historical duplicates | new or hardened tests should replace softer legacy slices in regular execution |
| preserve multi-line tests | tests that feed several lines are valuable because they keep the pack compact without becoming too shallow |
| keep registry completeness outside the core | tests can leave the regular run surface without being deleted from the system |

## Proposed steady-state core execution pack

| `#` | Test | Tier | Primary role-line coverage | Why it stays core |
|---|---|---|---|---|
| `1` | `T01` | core | `L01` | baseline repo-understanding anchor |
| `2` | `T03` | core | `L02`, `L03` | strong design-plus-risk reasoning anchor |
| `3` | `T05` | core | `L04`, `L05`, `L09` | reusable review and UI-static bridge |
| `4` | `T07` | core | `L03`, `L07` | stronger systems and risk pressure than softer legacy neighbors |
| `5` | `T08` | core | `L06`, `L07`, `L09` | broad implementation anchor |
| `6` | `T09` | core | `L06`, `L07`, `L08` | root-cause and ownership anchor |
| `7` | `T10` | core | `L02`, `L08`, `L10` | resume and long-horizon hybrid anchor |
| `8` | `T12` | core | `L01` | sharper source-of-truth confirmation than keeping all repo-understanding slices active |
| `9` | `T15` | core | `L07`, `L08` | normalized systems and toolchain bridge |
| `10` | `T18` | core | `L05` | non-browser static UI review anchor |
| `11` | `T19` | core | `L04` | explicit code-and-quality review anchor |
| `12` | `T21` | core | `L06`, `L09` | UI-facing worker implementation confirmation |
| `13` | `T22` | core | `L08`, `L10` | build-owner discovery and autonomy pressure |
| `14` | `T23` | core | `L09`, `L10` | UI continuity and long-horizon bridge |
| `15` | `T24` | core | `L10` | explicit multi-step persistence pressure |
| `16` | `T25` | core | `L07`, `L08`, `L10` | messy ownership and anti-brittleness anchor |
| `17` | `T29` | core | `L08` | stronger toolchain false-root ambiguity probe |
| `18` | `T30` | core | `L05`, `L09` | stronger static UI wrong-file-attraction probe |

## Extended pack

| Test | Tier | Why it moves out of steady-state core |
|---|---|---|
| `T02` | extended | useful for design/research confirmation, but covered enough by `T01`, `T03`, `T10`, and `T12` in the core |
| `T04` | extended | narrow design slice; good for confirmation, not needed every run |
| `T06` | extended | softer risk-only slice than `T03` plus `T07` |
| `T11` | extended | early role-gap design signal that becomes redundant once core design anchors are hardened |
| `T13` | extended | architecture/risk confirmation rather than required steady-state anchor |
| `T14` | extended | same role as `T13`; better as tie-break evidence |
| `T16` | extended | implementation confirmation already largely covered by `T08`, `T09`, `T21` |
| `T17` | extended | UI implementation confirmation already largely covered by `T21`, `T23`, `T30` |
| `T20` | extended | static visual confirmation already covered by `T18`, `T30`, and `T05` |
| `T26` | extended | useful toolchain confirmation, but `T15`, `T22`, `T25`, `T29` form a stronger steady-state set |
| `T27` | extended | long-horizon confirmation retained for later tie-breaks |
| `T28` | extended | long-horizon confirmation retained for later tie-breaks |

## Incubation tests

| Test | Tier | Current read |
|---|---|---|
| `T31` | incubation | keep outside steady-state until fallback overlays are worth regular execution again |
| `T32` | incubation | promising stronger worker probe, but not yet needed before the current core is fully hardened |
| `T33` | incubation | promising UI/decorative probe, but not yet needed before the current core is fully hardened |

## Steady-state line coverage

| Line | Core basis |
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

## Operating rule

| Situation | Use |
|---|---|
| regular reruns and ranking refresh | steady-state core execution pack |
| suspicious ties or unexpected rank flips | add targeted tests from the extended pack |
| fallback-overlay research or new probe admission | use incubation tests explicitly and separately |

## Next execution implication

The near-term implementation order should build the worker-heavy part of the core first:

1. `T08`
2. `T09`
3. `T10`
4. `T22`
5. `T23`
6. `T24`
7. `T25`
8. `T29`
9. `T30`

Then complete the advisory, review, and static-core anchors:

10. `T01`
11. `T03`
12. `T05`
13. `T07`
14. `T12`
15. `T15`
16. `T18`
17. `T19`
18. `T21`
