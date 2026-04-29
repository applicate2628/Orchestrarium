# Scoring Anchors

Pass requires the candidate to satisfy all stateful invariants in the verifier:

- no input mutation
- causal plan order
- idempotent completed reruns
- per-batch checkpoint isolation
- resume after crash
- current-attempt rollback only
- retry queue causal order
- global journal sequence
- event-log based reporting

Runtime failures and protected-surface edits are not model correctness passes.
