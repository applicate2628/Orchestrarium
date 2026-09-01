# Accepted Performance Budgets And Decisions

These are already accepted by the team. They are NOT findings; raising them is a false positive.

## Accepted: fixed retry backoff

`fetch_with_backoff` sleeps 50ms between attempts. This backoff is mandated by the upstream rate
contract to avoid tripping the provider's rate limiter. It is a required, bounded delay on the retry
path (not the success path) and is explicitly accepted. Do not flag the `time.sleep` backoff.

## Accepted: import-time build stamp

`BUILD_STAMP` is read once from a small file at module import. It is evaluated a single time when the
process starts, not per request. One-time import-time I/O is accepted. Do not flag it as hot-path I/O.

## Accepted: known-lane membership check

`KNOWN_LANES` is a fixed six-element tuple. The `lane in KNOWN_LANES` membership check runs at most
once per request over six constant elements; its cost is constant and negligible. Converting it to a
set is a micro-preference, not a performance defect. Do not flag it.

## In scope (report if defective)

- Per-request construction of expensive objects on the hot path.
- Super-linear (e.g. quadratic) work in batch size.
- Unbounded per-process memory growth.
- Eager/unconditional serialization work that is usually discarded.
