# False-Positive Traps (private)

These are intentionally present and look like performance defects but are not. Raising any of them
(as a findings-table row) fails the review. They are the near-peer separators: a strong-but-slightly-
weaker reviewer flags a surface "perf smell" instead of tracing real cost.

## D1 - KNOWN_LANES tuple "should be a set"

- `config.py:6` `KNOWN_LANES = (...)`; `aggregator.py:21` `if lane in KNOWN_LANES`.
- Fixed 6-element tuple, checked at most once per request. Constant cost. Converting to a set is a
  micro-preference, not a defect. Accepted in `inputs/accepted-performance-budgets.md`.

## D2 - Import-time build-stamp read "I/O in hot path"

- `config.py:19` `BUILD_STAMP = _read_build_stamp()`; reads a small file.
- Evaluated ONCE at module import, not per request. Not hot-path I/O. Accepted.

## D3 - Retry backoff "blocking sleep"

- `aggregator.py:43` `time.sleep(0.05)` inside `fetch_with_backoff`.
- Mandated upstream rate-contract backoff on the retry (not success) path. Accepted.

## Enforcement

- Any findings-table row whose Title matches a forbidden keyword set fails.
- The `## False Positives Avoided` section MUST explicitly name `known_lanes`, `backoff`, and
  `build stamp` as consciously rejected, so silence about the traps is not rewarded.
