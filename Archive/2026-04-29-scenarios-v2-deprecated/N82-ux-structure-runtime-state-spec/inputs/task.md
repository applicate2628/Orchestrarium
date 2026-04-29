# UX Runtime State Spec Task

Produce one UX-owned runtime state specification for the ConsoleShip publish workflow.

Editable surface: `candidate/ux-state-spec.json`

Required artifact: valid JSON object with these top-level keys in this order:

1. `spec_id`
2. `role_owner`
3. `state_model`
4. `breakpoint_invariants`
5. `affordance_rules`
6. `copy_ledger`
7. `handoff_contracts`
8. `non_goals`

Do not write code. Do not specify components, CSS classes, API payloads, tests, routes, or
implementation steps. Stay at the UX structure level: state names, visible cues, priority, forbidden
visual affordances, and handoff boundaries.
