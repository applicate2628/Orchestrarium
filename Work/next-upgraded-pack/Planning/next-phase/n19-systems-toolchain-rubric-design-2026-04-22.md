# N19 Systems Toolchain Rubric Design

Date: 2026-04-22
Owner: `$lead`
Status: `PASS`

## Purpose

Add a diagnostic systems/toolchain implementation pilot after the scorecard showed that
`worker.systems-performance-implementation` was still baseline-heavy.

## Scenario

`N19-systems-toolchain-cache-gauntlet` tests a toolchain-owned build-gate package. The candidate
must repair profile/env precedence, path normalization, cache key portability, dependency ordering,
feature conflict rejection, cache-hit reporting, source trace, and lock cleanup.

## Scoring

The binary verifier is authoritative for correctness. The post-run scorer adds a diagnostic rubric:

| Dimension | Points |
|---|---:|
| binary correctness | `40` |
| patch quality | `30` |
| elapsed proxy | `15` |
| output-size cost proxy | `15` |

This is a role-fit signal, not a replacement for the full-v2 denominator.
