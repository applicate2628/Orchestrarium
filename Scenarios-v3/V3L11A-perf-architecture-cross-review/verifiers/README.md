# Verifier

`check_perf_architecture_review.py` - deterministic, read-only, executes no candidate code.

## Modes

- `--bundle-shape-only` - validate the bundle contract and scenario.yaml metadata.
- (default) - validate the completed `candidate/review-report.md` against the findings-table oracle.
- `--changed-path PATH` (repeatable) - assert only the allowed change surface was touched.

## Four-probe validation

1. Reference PASS: copy `oracle/reference/review-report.md` over `candidate/review-report.md` -> PASS.
2. Vacuous FAIL: a keyword-stuffed report with the section headers but no valid findings table -> FAIL.
3. Decoy FAIL: an adversarial report that flags the three planted decoys (tuple->set, import read,
   backoff) instead of / in addition to the real findings -> FAIL on forbidden traps and/or exact count.
4. Near-peer separation: the exact_finding_count (4) + forbidden traps + distinct-row + cross-file
   evidence binding split a top reviewer from a near-peer who misses the quadratic or flags a decoy.
