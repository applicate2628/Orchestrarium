# ADR-022: Retry Policy v3

Status: accepted

RetryBox runtime policy is `retry-policy-v3`.

The approved runtime algorithm is `bounded-exponential`.

The accountable owner for retry behavior is `sre-reliability`.

Changing retry attempts, backoff values, retry owner, or customer-visible export semantics requires
product re-intake before implementation.

Rollback to `legacy-linear` was rejected because it hides partial outage signals and conflicts with
the incident-budget model.
