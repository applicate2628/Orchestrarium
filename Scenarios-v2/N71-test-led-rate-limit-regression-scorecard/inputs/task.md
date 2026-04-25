# Task

Fix the fixed-window rate-limit regression and add a focused regression test.

Allowed edits:

- `candidate/workspace/src/flowlimit/limiter.py`
- `candidate/workspace/tests/test_window_regression.py`
- `candidate/test-ledger.json`

Do not edit visible tests, models, package exports, README files, oracle files, verifier files, or
scenario metadata.

Required behavior:

- rate-limit state must be isolated by `(tenant_id, user_id, route, window_index)`
- two users in the same tenant and route must not consume each other's budget
- retry-after for a denied request must be the remaining seconds until the current window ends
- a request exactly on the next window boundary must use the new window
- do not mutate `RateLimitRequest`
- keep the implementation small and dependency-free
- add a meaningful regression test in `tests/test_window_regression.py`; it must cover same-tenant
  different-user isolation, window boundary behavior, and `retry_after`
- update `test-ledger.json` with exact changed files, behavior fixes, regression-test coverage, and
  patch-quality statement

The visible test is intentionally insufficient. The verifier checks hidden behavior and the required
test artifact.
