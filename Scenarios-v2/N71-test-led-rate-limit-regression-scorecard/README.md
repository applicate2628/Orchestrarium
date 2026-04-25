# N71 Test-Led Rate Limit Regression Scorecard

W49 implementation scorecard for a test-led regression repair.

The starter limiter passes a visible happy path but leaks rate-limit state across users in the same
tenant and returns an imprecise retry-after value. The task requires both the production fix and a
meaningful regression test artifact.
