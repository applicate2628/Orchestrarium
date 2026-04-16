Date: 2026-04-16
Owner: `$lead`
Status: `PASS`

## Purpose

This file marks the rows and overlays that most deserve hardening pressure in the next phase.

## Suspicious rows

| Row | Current basis order | Why it is suspicious | Next-phase treatment |
|---|---|---|---|
| `O04 / legacy W4` fallback mechanical admissibility | `X2` only active top row | current read is too narrow and fallback-heavy; it may flatter a model that is merely mechanically compliant | design a harder fallback probe that requires rejection of tempting but wrong local fixes |
| `O05 / legacy W5` fallback reasoning expansion | `X2` only active top row | same concern as `O04`, but with more reasoning surface | add a fallback probe with ambiguous evidence and explicit anti-drift constraints |
| `L06 worker.general-implementation` | `X1 > X4 > X2 > X3 > X5` | `X4` is high but frozen; `X2 > X3` remains worth challenging | stress active cohort now; defer `X4` fairness rerun |
| `L07 worker.systems-implementation` | `X1 > X4 > X2 > X3 > X5` | same shape as general implementation; may still underrate `X3` on harder ownership-aware tasks | design a nastier implementation probe with shared-state or owner-boundary traps |
| `L08 worker.toolchain-root-ownership` | `X1 > X2 > X3 > X5 > X4` | `X2 > X3` is plausible but still needs harder false-root pressure; `X4` is already weak here | active hardening target |
| `L09 worker.ui-implementation` | `X1 > X4 > X2 > X3 > X5` | `X4` placement is frozen and `X2 > X3` may be an artifact of easier static tasks | harder non-browser UI design target |

## Lower-priority rows

| Row | Reason not first |
|---|---|
| `L01..L04` advisory, design, and review-heavy rows | current top ordering looks stable enough to avoid being the first hardening target |
| `T18 / legacy G08` static UI evidence | already redesigned once and now useful; deepen later only if it stops separating the active cohort |
| `T25 / legacy G15` messy worker ownership | already has useful separation; extend only after bounded-worker rows are clearer |
