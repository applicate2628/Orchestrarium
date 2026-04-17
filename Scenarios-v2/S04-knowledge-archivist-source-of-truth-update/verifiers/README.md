# Verifiers

`check_source_of_truth_update_packet.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to
  validate the materialized bundle itself.
- default mode checks whether a scored run completed the source-of-truth update packet correctly.

## What the full verifier expects after a run

- `candidate/source-of-truth-update-packet.md` keeps the required stewardship sections
- the packet cites the accepted canonical sources and the three exact update targets
- the packet includes reconciliation work plus archive hygiene actions
- the packet keeps governance and policy surfaces read-only and names the escalation boundary
- the packet ends with an allowed stewardship outcome and no `TODO` markers remain

The verifier is intentionally stewardship-specific. It is not a generic markdown linter, planner
checker, or implementation verifier.
