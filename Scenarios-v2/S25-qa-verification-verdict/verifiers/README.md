# Verifiers

`check_qa_verdict.py` supports two modes:

- `--bundle-shape-only` checks the fixture author's bundle contract. This is the mode used to
  sanity-check the materialized bundle itself.
- default mode checks whether a scored run completed the QA verdict correctly.

## What the full verifier expects after a run

- `candidate/qa-verdict.md` exists, has the required QA sections, and contains no `TODO` markers
- the report maps `AC1..AC4` to evidence
- the report identifies the dry-run defect as a `regression`
- the report calls out the missing `--text-summary` nearby smoke coverage
- the report records the performance smoke as a pass
- the report includes the bug-registry expectation and ends with `REVISE`

The verifier is intentionally QA-specific. It checks role-correct anchors rather than prose style.
