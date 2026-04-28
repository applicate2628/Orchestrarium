# Task: Staged Interface Migration With Downstream Reentry

The package under `candidate/workspace/src/subscriptionmesh` currently exposes three legacy APIs
with ambiguous return values:

- `CustomerDirectory.get_customer(customer_id)` returns a customer dictionary or `None`.
- `SubscriptionPolicy.check(customer, request)` returns `True` or a string reason.
- `WebhookPublisher.publish(event)` returns a boolean and may raise transport exceptions.

Refactor them to structured APIs and migrate all internal consumers in one staged re-entry packet.
The hidden gate runs a downstream SDK consumer that imports only the public `subscriptionmesh`
package exports, so internal module-only fixes are not enough.

Required public APIs after migration:

- `CustomerDirectory.lookup_customer(customer_id, *, at_tick=None) -> CustomerLookup`
- `SubscriptionPolicy.evaluate_subscription(lookup, request) -> SubscriptionDecision`
- `WebhookPublisher.publish_webhook(event, decision) -> WebhookPublishResult`

Required structured result models:

- `CustomerLookup`: `found`, `customer_id`, `customer`, `reason`, `owner`, `source_ids`
- `SubscriptionDecision`: `allowed`, `reason`, `owner`, `source_ids`
- `WebhookPublishResult`: `accepted`, `status`, `retryable`, `event_id`, `error_code`, `owner`, `reason`, `source_ids`

Compatibility requirements:

- Remove the old public methods. Do not keep `get_customer`, `check`, or `publish` as wrappers.
- Export the structured result models and migrated consumer entry points from the package root:
  `CustomerLookup`, `SubscriptionDecision`, `WebhookPublishResult`, `handle_subscription_event`,
  `process_subscription_request`, `build_subscription_summary`, and `migrate_legacy_event`.
- Preserve observable behavior for missing customers, suspended customers, expired subscriptions,
  disabled tenants, missing feature entitlement, denied-without-webhook, webhook timeout, duplicate
  event IDs, legacy event migration, and accepted webhook publish.
- Preserve downstream SDK semantics: dataclass instances must serialize with `dataclasses.asdict`,
  denied events must not publish, timeout results must stay retryable, duplicate event IDs must not
  republish, legacy event envelopes must migrate without losing tenant/customer/source data, and
  summary reporting must accept structured result objects as well as dictionaries.
- Migrate the consumers in `service.py`, `api.py`, `reporting.py`, `legacy_adapter.py`, package
  exports, and visible tests.
- Update `candidate/source-ledger.json`, `candidate/migration-state.json`,
  `candidate/review-response.json`, `candidate/reentry-state.json`, and `candidate/closure.json`.
- Keep the source and migration ledgers source-bound to `S1`..`S12`, stale-source rejections from
  `source-conflict.md`, interface map, call-site migration, compatibility matrix, validation
  markers including the hidden downstream SDK gate, and exact changed-path budget.
- Resolve every item in `inputs/review-feedback.md` with decision, owner, and validation cue.

The verifier runs hidden repo-style consumers, hidden downstream SDK consumers, clean-room package
imports, source/reentry ledger checks, and exact scope checks. Passing only the visible starter test
is not enough.
