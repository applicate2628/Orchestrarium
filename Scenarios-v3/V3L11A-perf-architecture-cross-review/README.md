# V3L11A - Performance And Architecture Cross-Review

Target line: `L11` (performance-architecture review). Second L11 discriminator alongside S28
(build-plan F5 / A4); S28 uses a JavaScript target, this uses an independent Python package.

The candidate reviews `candidate/review-target/lane_aggregator/` for performance and architecture
defects on the request hot path and produces a findings-only report. A findings-table oracle binds
each real defect to `file:line`, exact severity/category, and evidence terms; an exact finding count;
three forbidden false-positive traps; and required false-positive-boundary terms.

## Why this separates near-peer strong reviewers (not merely hard)

The all-P L11 slots are already strong verifiers - hardness is not the gap, near-peer SEPARATION is.
This slot is engineered so that:

- F1 (per-request `LaneStore` rebuild) requires tracing cost across files into `store.py`.
- F2 (quadratic sibling re-resolve) is hidden inside an innocent list comprehension.
- Three planted decoys (tuple->set, import-time read, mandated backoff) are surface "perf smells"
  that a near-peer weaker reviewer plausibly flags.

The `exact_finding_count` (4) + `forbidden_findings` + distinct-row matching + cross-file evidence
binding is the separation mechanism: a top reviewer lands exactly four real findings and rejects three
decoys; a near-peer reviewer misses the quadratic or flags a decoy and fails a gate.

## Layout

- `inputs/` - task, accepted budgets (decoys are accepted here), boundary, architecture notes.
- `candidate/review-target/` - the Python package under review (read-only).
- `candidate/review-report.md` - the editable report (blank start state).
- `oracle/` - contract, expected findings, false-positive traps, anchors, and a passing `reference/`.
- `verifiers/check_perf_architecture_review.py` - deterministic, read-only, executes no candidate code.

## Terms and Abbreviations

- `hot path` - code run once per inbound request batch.
- `n-plus-one` / `N+1` - repeating a per-item expensive operation instead of doing it once.
- `L11` - the performance-architecture review routing line of the RF12 scorecard.
