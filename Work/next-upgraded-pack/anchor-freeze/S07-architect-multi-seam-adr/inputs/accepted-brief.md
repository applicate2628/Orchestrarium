# Accepted Brief

## Problem

The v2 benchmark redesign needs a repeatable way to author architect scenarios that grade the
quality of a multi-seam ADR choice. A bundle author must be able to declare:

- the admissible seam or seams
- the required tradeoff coverage
- the dependency-direction expectations
- the protected surfaces that must remain untouched

The accepted materialization plan already fixes `S07` as a design-packet bundle for `R07
$architect`. The open question is where those design-specific rules should live.

## Requirements

1. Preserve the universal `scenario.yaml` contract from `pack-specs-v1`.
2. Keep `S07` self-contained inside its bundle root.
3. Keep the candidate change surface limited to one ADR or design package file.
4. Do not move design semantics into adapter or implementation bundles.
5. Do not require a scoring-profile rewrite to support one design scenario.
6. Produce a design that a planner can consume without reopening the architecture choice.

## Success read

The accepted design should let future design bundles express scenario-local architecture anchors
without forcing changes to the role matrix, score profiles, publication tables, or bundle-path
conventions.
