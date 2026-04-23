# Phase 02 - Interface Migration

Fresh worker session. Resume only from files in the run root. Read
`candidate/migration-state.json` before editing.

Repair the InterfaceFlow runtime and visible tests:

- Replace legacy methods with `SessionStore.lookup`, `PolicyEvaluator.evaluate_policy`, and
  `EventRouter.dispatch_event`.
- Add structured dataclass result models for lookup, policy, and dispatch.
- Do not keep `get`, `evaluate`, or `dispatch` wrappers.
- Preserve missing, expired, revoked, blocked tenant, requires-admin, denied-without-dispatch,
  timeout, duplicate, and accepted event behavior.
- Migrate `orchestrator.py`, `api.py`, `report.py`, package exports, and tests.

Edit only the allowed source files, `candidate/workspace/tests/test_interfaceflow.py`, and
`candidate/migration-state.json`.

Tests should include these function names:

- `test_lookup_missing_session_contract`
- `test_router_timeout_is_retryable`
- `test_legacy_methods_removed`
- `test_denied_policy_does_not_dispatch`
- `test_report_counts_retryable_and_owners`

Run `python candidate/workspace/tests/test_interfaceflow.py` before finishing and append the
command to `candidate/migration-state.json`.
