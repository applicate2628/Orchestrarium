# Verifiers

`check_algorithm_invariant_proof_memo.py` supports two modes:

- `--bundle-shape-only` checks the author-side bundle contract for `S10`
- default mode checks whether a scored run completed `candidate/algorithm-invariant-proof-memo.md`

## What the full verifier expects after a run

- all required memo sections are present
- `D1` through `D4` are named
- `AS1` through `AS3` are named
- `A1` through `A3` are named
- `I1` through `I5` are named
- `X1` through `X5` are named
- `T1` through `T5` are named
- `E1` through `E5` are cited somewhere in the memo
- the memo includes the phrases `affected subgraph`, `stable tie-break`, and `cycle witness`
- the numbered claims section has at least five claims
- the final gate decision is `PASS`
- no `TODO` markers remain

The verifier is intentionally scenario-specific. It checks proof-memo completeness and role
fidelity, not generic markdown quality.
