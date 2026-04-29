# Verifiers

`check_model_validation_memo.py` supports two modes:

- `--bundle-shape-only` checks the author-side bundle contract for `S11`
- default mode checks whether a scored run completed `candidate/model-validation-memo.md`

## What the full verifier expects after a run

- all required memo sections are present
- `EQ1` through `EQ3` are named
- `AS1` through `AS4` are named
- `IV1` through `IV4` are named
- `V1` through `V5` are named
- `L1` through `L4` are named
- `E1` through `E5` are cited somewhere in the memo
- the memo includes the phrases `lumped-capacitance`, `energy balance`, `steady-state`,
  `time constant`, `sensor lag`, and `fan regime`
- the numbered claims section has at least five claims
- the final gate decision is `REVISE`
- no `TODO` markers remain

The verifier is intentionally scenario-specific. It checks model-validation memo completeness and
role fidelity, not generic markdown quality.
