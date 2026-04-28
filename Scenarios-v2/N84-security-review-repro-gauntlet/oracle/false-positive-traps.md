# False Positive Traps

The JSON report must list these under `falsePositiveAvoided` and must not use any of them as
finding reproduction cases.

| Case | Pattern | Required reason |
|---|---|---|
| `B1` | `MASKED_EXAMPLE_TOKEN`, `sk_test_example` | synthetic fixture text is not propagated to a sink |
| `B2` | `rel="noopener"` | acceptable link hardening |
| `B3` | `GET /health` | intentionally public and no privileged disclosure |
