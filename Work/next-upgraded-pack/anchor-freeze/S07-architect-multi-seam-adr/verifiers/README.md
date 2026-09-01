# Verifiers

`check_design_packet.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to
  validate the materialized bundle itself.
- default mode checks whether a scored run completed the architect design package correctly.

## What the full verifier expects after a run

- `candidate/design-package.md` has all required architect sections and subsections
- the package chooses `Option B - bundle-local oracle and verifier seam`
- the package explicitly rejects `Option A` and `Option C`
- dependency direction, `scenario.yaml`, `design-contract.json`, verifier ownership, and the shared
  score profile are all mentioned
- the numbered claims section is present and no `TODO` markers remain
- the package ends with a valid gate decision and does not contain implementation-code markers

The verifier is intentionally architect-specific. It is not a generic markdown linter or planner
checker.
