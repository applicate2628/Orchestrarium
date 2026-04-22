Date: 2026-04-22
Owner: `$lead`
Status: `PASS`

## Purpose

`N18-scientist-constraints-decision-gauntlet` fills the scientist/constraint role-fit gap. It
requires a bounded decision under conflicting performance, security, reliability, stale-source, and
non-claim constraints.

## Pressure

| Area | Required behavior |
|---|---|
| hard constraints | preserve exact p95, false-negative, source-trace, memory, and secret-handling limits |
| decision | choose only `Option C - keyed index plus exact ledger replay` |
| rejection logic | reject `Option A` for p95 latency and `Option B` for rollback false negatives |
| non-claim discipline | reject UI smoothness and stale benchmark notes as safety evidence |
| falsification | include latency, false-negative, source-trace, and memory checks with owners |

## Expected Use

Run `X1` and `X3` first, then add `X2`, `X5`, and `X6` calibration only when runtime health allows.
