# Task

Patch the `ledgerpatch` reconciliation hot path.

Required outcome:

- Preserve the public API: `LedgerEvent`, `LedgerRow`, `build_account_ledger(events)`, and
  `summarize_ledger(rows)`.
- Fix duplicate event semantics: if the same `event_id` appears more than once, use only the version
  with the highest `sequence`.
- Fix void semantics: a `void` event with `voids_event_id` removes the referenced latest event from
  totals, and the void event itself is not counted as revenue.
- Preserve refund semantics: refunds subtract `amount_cents`.
- Keep totals partitioned by `(account_id, period, currency)`.
- Do not mutate input events.
- Keep the hot path fast for large batches. Use a single-pass or indexed approach; do not scan the
  whole event list for every event.
- Fill `candidate/patch-quality-ledger.json` with concise evidence of the changed files, hidden
  semantics covered, runtime budget, and patch-quality constraint.

Allowed edits:

- `candidate/workspace/src/ledgerpatch/reconcile.py`
- `candidate/patch-quality-ledger.json`

Do not edit visible tests, models, reporting, inputs, oracle, or verifiers.
