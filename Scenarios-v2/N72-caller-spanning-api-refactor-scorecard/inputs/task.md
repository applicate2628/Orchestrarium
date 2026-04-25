# Task

Complete the `AccountRef` API refactor across all caller surfaces.

Allowed edits:

- `candidate/workspace/src/billinglink/service.py`
- `candidate/workspace/src/billinglink/api.py`
- `candidate/workspace/src/billinglink/cli.py`
- `candidate/workspace/src/billinglink/reports.py`
- `candidate/refactor-ledger.json`

Do not edit tests, models, package exports, README files, oracle files, verifier files, or scenario
metadata.

Required behavior:

- accept schema-v2 API payloads with `account.id` and `account.region`
- preserve legacy API payloads with `customer_id`
- preserve input payload immutability
- propagate `region`, `currency`, and `source` through service, API, CLI, and report rows
- `AccountRef` inputs must produce `source: "api-v2"`
- legacy `customer_id` inputs must use default region `us` and `source: "api-legacy"`
- keep the implementation dependency-free and small
- update `refactor-ledger.json` with exact changed files, caller surfaces, compatibility behavior,
  migration notes, and patch-quality statement

The visible tests are intentionally insufficient. Hidden verification exercises API, CLI, report, and
compatibility callers.
