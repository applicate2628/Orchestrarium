# Task: Structured Interface Refactor

The package under `candidate/workspace/src/interfaceflow` currently exposes three legacy
interfaces with ambiguous return values:

- `SessionStore.get(session_id)` returns a record dictionary or `None`.
- `PolicyEvaluator.evaluate(record, event)` returns a boolean or a string reason.
- `EventRouter.dispatch(event)` returns a boolean and may raise transport exceptions.

Refactor them to structured interfaces and migrate all internal consumers.

Required public interfaces:

- `SessionStore.lookup(session_id, *, at_tick=None) -> SessionLookup`
- `PolicyEvaluator.evaluate_policy(lookup, event) -> PolicyDecision`
- `EventRouter.dispatch_event(event, decision) -> DispatchResult`
- `api.handle_event_batch(records, rules, transport, requests, at_tick=None) -> list[dict]`

Required structured result models:

- `SessionLookup`: `found`, `session_id`, `record`, `reason`, `owner`
- `PolicyDecision`: `allowed`, `reason`, `owner`, `source_ids`
- `DispatchResult`: `accepted`, `status`, `retryable`, `event_id`, `error_code`, `owner`

Compatibility requirements:

- Remove the old public methods. Do not keep `get`, `evaluate`, or `dispatch` as wrappers.
- Preserve observable behavior for missing, expired, revoked, blocked, timeout, duplicate, and
  accepted events.
- Migrate the consumers in `orchestrator.py`, `api.py`, `report.py`, batch API handling,
  structured audit reporting, and visible tests.
- `handle_event_batch` must preserve request order, annotate each result with `batch_index`, avoid
  dispatching rejected requests, and avoid resending duplicate event IDs.
- `report.build_audit_summary` must accept both dictionaries and structured result objects.
- Update `candidate/refactor-ledger.json` with the old-to-new interface map, call-site migration
  rows, compatibility matrix, and validation commands.

The verifier will run hidden consumer cases. Passing only the visible starter test is not enough.
