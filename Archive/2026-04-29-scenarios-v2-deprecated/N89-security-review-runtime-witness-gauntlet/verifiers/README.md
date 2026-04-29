# N89 Verifiers

- `check_security_runtime_witness_review.py --bundle-shape-only` validates the bundle contract.
- `check_security_runtime_witness_review.py --expect-start-state` checks that the starter report
  still fails for the intended reasons.
- `check_security_runtime_witness_review.py` validates changed-path scope, JSON report shape,
  exact vulnerability tuples, executable witness matrix rows, false-positive exclusions, and gate
  decision.
