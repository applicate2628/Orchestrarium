# Expected Findings (private)

Four genuine performance/architecture defects. Exactly these; no more, no fewer.

## F1 - LaneStore re-instantiated per request (blocking, hot-path / n-plus-one)

- `aggregator.py:18`: `store = LaneStore(LANE_CONFIG_PATH)` inside the per-request loop.
- The cost is cross-file: `store.py` `LaneStore.__init__` calls `_read_config` (reparse) and
  `_build_lane_index` (full index rebuild) on every construction. Should be built once per batch.
- A near-peer reviewer who assumes `LaneStore(...)` is cheap and never opens `store.py` misses this.

## F2 - Quadratic sibling re-resolve (blocking, complexity / scalability)

- `aggregator.py:20`: the `siblings` comprehension calls `resolve_lane` over ALL requests for EACH
  request -> O(n^2) in batch size (compounded by F1 if the store is also rebuilt).
- Hidden inside an innocent-looking list comprehension; the quadratic is the separator.

## F3 - Unbounded snapshot history (major, memory)

- `aggregator.py:27` (declared at `:8`): `_SNAPSHOT_HISTORY.append(json.dumps(rows))` grows for the
  whole process lifetime with no bound. Steady-state memory growth.

## F4 - Unconditional debug serialization (major, serialization / waste)

- `aggregator.py:26`: `json.dumps(rows)` is evaluated unconditionally and passed to `logger.debug`,
  so the serialization cost is paid on every batch even when debug logging is disabled.

## Not required, not forbidden

- The `else` unassigned branch and the exception class are correctness/design, not perf; neither is a
  required finding, and neither is a planted trap. A report that omits them is still correct.
