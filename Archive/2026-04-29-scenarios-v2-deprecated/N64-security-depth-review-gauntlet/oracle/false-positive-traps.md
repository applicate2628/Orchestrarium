# False Positive Traps

- `MASKED_EXAMPLE_TOKEN = "sk_test_example_do_not_use"` is synthetic fixture text and is not a live
  secret exposure by itself.
- `rel="noopener"` on the documentation link is acceptable hardening, not a vulnerability.
- `GET /health` returning `{ "ok": true }` is intentionally public and does not disclose privileged
  state.
