# Phase 02 - API Migration

Fresh worker session. Resume only from files in the run root. Read
`candidate/migration-state.json` before editing.

Repair the BillingMesh runtime and visible tests:

- Replace legacy methods with `AccountDirectory.lookup_account`,
  `EntitlementPolicy.evaluate_entitlement`, and `UsagePublisher.publish_usage`.
- Add structured dataclass result models for lookup, entitlement, and publishing.
- Do not keep `get_account`, `check`, or `publish` wrappers.
- Preserve missing-account, suspended-account, plan-expired, tenant-disabled,
  feature-not-entitled, denied-without-publish, usage-publish-timeout, duplicate-usage, and
  accepted-usage behavior.
- Migrate `service.py`, `api.py`, `reporting.py`, package exports, and tests.

Edit only the allowed source files, `candidate/workspace/tests/test_billingmesh.py`, and
`candidate/migration-state.json`.

Tests should include these function names:

- `test_lookup_missing_account_contract`
- `test_publisher_timeout_is_retryable`
- `test_legacy_methods_removed`
- `test_denied_entitlement_does_not_publish`
- `test_report_counts_queued_duplicate_and_owners`

Run `python candidate/workspace/tests/test_billingmesh.py` before finishing and append the command
to `candidate/migration-state.json`.
