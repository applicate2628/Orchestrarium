Date: 2026-04-22
Owner: `$lead`
Status: `PASS`

## Purpose

`N17-owner-orchestration-routing-gauntlet` is the first scored owner/orchestration pilot for the
role-fit program. It tests whether a row can preserve the active benchmark task, classify
interruptions, keep diagnostic overlays separate from routing lanes, route the next owner/gates
correctly, and define bounded `X2`/`X5`/`X6` calibration policy.

## Design

| Area | Pressure |
|---|---|
| primary task continuity | role-fit routing remains active; no global winner collapse |
| diagnostic separation | `N16` remains `E6` diagnostic evidence, not core routing policy |
| role routing | `$lead` owns the immediate next step; QA and architecture review are later gates |
| calibration policy | X2/X5/X6 run only when lane policy could change, with X5 smoke guard |
| runtime semantics | quota/timeouts remain `NOT-RUN`, not model failures |

## Expected Use

Run `X1` and `X3` first. Add `X2`, `X5`, and `X6` only as calibration rows after the bundle is
validated and runtime health is acceptable.
