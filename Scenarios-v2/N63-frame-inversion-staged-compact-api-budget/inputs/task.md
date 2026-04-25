# Task: Staged Frame-Inversion Real-Repo Billing API Migration

The package under `candidate/workspace/src/billingmesh` currently exposes three legacy APIs with
ambiguous return values:

- `AccountDirectory.get_account(account_id)` returns an account dictionary or `None`.
- `EntitlementPolicy.check(account, request)` returns `True` or a string reason.
- `UsagePublisher.publish(event)` returns a boolean and may raise transport exceptions.

Refactor them to structured APIs and migrate all internal consumers. Treat the work as four explicit
stages: intake/migration plan, API migration, review-response resolution, and final re-entry
closeout.

Required public APIs after migration:

- `AccountDirectory.lookup_account(account_id, *, at_tick=None) -> AccountLookup`
- `EntitlementPolicy.evaluate_entitlement(lookup, request) -> EntitlementDecision`
- `UsagePublisher.publish_usage(event, decision) -> PublishResult`

Required structured result models:

- `AccountLookup`: `found`, `account_id`, `account`, `reason`, `owner`
- `EntitlementDecision`: `allowed`, `reason`, `owner`, `source_ids`
- `PublishResult`: `accepted`, `status`, `retryable`, `usage_id`, `error_code`, `owner`, `reason`

Compatibility requirements:

- Remove the old public methods. Do not keep `get_account`, `check`, or `publish` as wrappers.
- Preserve observable behavior for missing accounts, suspended accounts, expired plans, disabled
  tenants, missing feature entitlement, denied-without-publish, publisher timeout, duplicate usage
  IDs, and accepted usage.
- Migrate the consumers in `service.py`, `api.py`, `reporting.py`, package exports, and visible
  tests.
- Update `candidate/migration-state.json`, `candidate/review-response.json`, and
  `candidate/closure.json` so a fresh reviewer can reconstruct each stage, source decision, stale
  rejection, validation cue, and final closeout without relying on chat history.
- Keep `candidate/migration-state.json` source-bound: include source ids `S1`..`S10`, stale-source
  rejections from `decoy-map.md`, interface map, call-site migration, compatibility matrix,
  validation markers, and exact patch budget.
- Resolve every item in `inputs/review-feedback.md` with decision, owner, and validation cue.
- Keep worker output under the visible operator budget: `../meta/worker-output.txt <= 40000` bytes.
  The staged framing does not waive this low-noise budget.

The verifier will run hidden repo-style consumer cases, ledger checks, exact scope checks, and the
operator-budget check. Passing only the visible starter test is not enough.
