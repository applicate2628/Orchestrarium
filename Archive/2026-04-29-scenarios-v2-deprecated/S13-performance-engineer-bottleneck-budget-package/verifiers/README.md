# Verifiers

`check_performance_constraint_package.py` supports two modes:

- `--bundle-shape-only` checks the author-side bundle contract for `S13`
- default mode checks whether a scored run completed `candidate/performance-constraint-package.md`

## What the full verifier expects after a run

- all required package sections are present
- `B1` through `B5` are named
- `BT1` through `BT4` are named
- `MS1` through `MS5` are named
- `TB1` through `TB4` are named
- `C1` through `C5` are named
- `G1` through `G3` are named
- `E1` through `E5` are cited somewhere in the package
- the package includes the phrases `cold run`, `warm run`, `p95`, `peak RSS`, `hash manifest`,
  and `redaction`
- the numbered claims section has at least five claims
- the final gate decision is `REVISE`
- no `TODO` markers remain

The verifier is intentionally scenario-specific. It checks performance-constraint completeness and
role fidelity, not generic markdown quality.
