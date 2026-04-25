# Task: Compact Frame-Inversion Structured Interface Migration

The package under `candidate/workspace/src/interfaceflow` currently exposes three legacy
interfaces with ambiguous return values:

- `SessionStore.get(session_id)` returns a record dictionary or `None`.
- `PolicyEvaluator.evaluate(record, event)` returns a boolean or a string reason.
- `EventRouter.dispatch(event)` returns a boolean and may raise transport exceptions.

Refactor them to structured interfaces and migrate all internal consumers in one compact pass.

Required public interfaces after migration:

- `SessionStore.lookup(session_id, *, at_tick=None) -> SessionLookup`
- `PolicyEvaluator.evaluate_policy(lookup, event) -> PolicyDecision`
- `EventRouter.dispatch_event(event, decision) -> DispatchResult`

Required structured result models:

- `SessionLookup`: `found`, `session_id`, `record`, `reason`, `owner`
- `PolicyDecision`: `allowed`, `reason`, `owner`, `source_ids`
- `DispatchResult`: `accepted`, `status`, `retryable`, `event_id`, `error_code`, `owner`, `reason`

Compatibility requirements:

- Remove the old public methods. Do not keep `get`, `evaluate`, or `dispatch` as wrappers.
- Preserve observable behavior for missing, expired, revoked, blocked, requires-admin, timeout,
  duplicate, denied-without-dispatch, and accepted events.
- Migrate the consumers in `orchestrator.py`, `api.py`, `report.py`, and visible tests.
- Update `candidate/migration-state.json`, `candidate/review-response.json`, and
  `candidate/closure.json` in the same pass. These files must still be durable enough to reconstruct
  the staged migration, review decisions, source rejections, validation cues, and final closeout
  without relying on chat history.

The verifier will run hidden consumer cases and the same staged ledger checks as the long-frame
version. Passing only the visible starter test is not enough, and concise worker output does not
replace the required ledgers.
