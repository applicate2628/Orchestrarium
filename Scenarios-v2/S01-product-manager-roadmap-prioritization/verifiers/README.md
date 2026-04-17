# Verifiers

`check_roadmap_decision_package.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to
  validate the materialized bundle itself.
- default mode checks whether a scored run completed the roadmap decision package correctly.

## What the full verifier expects after a run

- `candidate/roadmap-decision-package.md` keeps the required decision sections and exact priority
  headings
- the package stays product-manager-owned and keeps the gate and rerun-window guardrails explicit
- the roadmap commits to the preferred top-two ordering and makes the deferrals explicit
- the package avoids product-analysis, advisory, lead-routing, and implementation markers
- the package ends with an allowed decision status and no `TODO` markers remain

The verifier is intentionally role-specific. It is not a generic markdown linter, product-analysis
checker, or implementation verifier.
