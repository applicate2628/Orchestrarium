# Verifiers

`check_interaction_state_flow_brief.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to
  validate the materialized bundle itself.
- default mode checks whether a scored run completed the interaction-state UX brief correctly.

## What the full verifier expects after a run

- `candidate/ux-structure-brief.md` keeps the required state-flow sections and ordered headings
- the brief stays focused on interaction-state flow, interruption handling, and return loops
- the brief explicitly treats resume cues, ownership, and cross-surface handoffs
- the brief names the implementation and review boundaries instead of drifting into those outputs
- the brief ends with an allowed status and no `TODO` markers remain

The verifier is intentionally role-specific. It is not a generic markdown linter, implementation
checker, architecture checker, or review verifier.
