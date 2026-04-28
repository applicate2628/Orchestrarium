# Task: Real Interface Migration With Hidden Downstream App

The package under `candidate/workspace/src/billingmesh` currently exposes three legacy APIs with
ambiguous return values:

- `AccountDirectory.get_account(account_id)` returns an account dictionary or `None`.
- `EntitlementPolicy.check(account, request)` returns `True` or a string reason.
- `UsagePublisher.publish(event)` returns a boolean and may raise transport exceptions.

Refactor them to structured APIs and migrate all internal consumers in one patch. The hidden gate
also runs a downstream app that imports only the public `billingmesh` package exports, so internal
module-only fixes are not enough.

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
- Export the structured result models and migrated consumer entry points from the package root:
  `AccountLookup`, `EntitlementDecision`, `PublishResult`, `handle_usage_event`,
  `process_usage_request`, and `build_usage_summary`.
- Preserve observable behavior for missing accounts, suspended accounts, expired plans, disabled
  tenants, missing feature entitlement, denied-without-publish, publisher timeout, duplicate usage
  IDs, and accepted usage.
- Preserve downstream-app semantics for public-only consumers: dataclass instances must serialize
  with `dataclasses.asdict`, denied events must not publish, timeout results must stay retryable,
  duplicate usage IDs must not republish, and summary reporting must accept structured result
  objects as well as dictionaries.
- Migrate the consumers in `service.py`, `api.py`, `reporting.py`, package exports, and visible
  tests.
- Update `candidate/migration-state.json`, `candidate/review-response.json`, and
  `candidate/closure.json` in the same compact patch.
- Keep `candidate/migration-state.json` source-bound: include source ids `S1`..`S10`, stale-source
  rejections from `decoy-map.md`, interface map, call-site migration, compatibility matrix,
  validation markers including the hidden downstream public-app gate, and exact changed-path budget.
- Resolve every item in `inputs/review-feedback.md` with decision, owner, and validation cue.

The verifier will run hidden repo-style consumer cases, hidden downstream public-app cases, ledger
checks, and exact scope checks. Passing only the visible starter test is not enough.
