# Verifiers

`check_security_constraint_package.py` supports two modes:

- `--bundle-shape-only` checks the author-side bundle contract for `S12`
- default mode checks whether a scored run completed `candidate/security-constraint-package.md`

## What the full verifier expects after a run

- all required package sections are present
- `TB1` through `TB5` are named
- `AB1` through `AB3` are named
- `C1` through `C6` are named
- `M1` through `M5` are named
- `V1` through `V4` are named
- `E1` through `E5` are cited somewhere in the package
- the numbered claims section has at least five claims
- the final gate decision is `REVISE`
- no `TODO` markers remain

The verifier is intentionally scenario-specific. It checks constraint-package completeness and
control coverage, not generic markdown quality.
