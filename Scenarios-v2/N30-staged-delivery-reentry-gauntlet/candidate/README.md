# Candidate Instructions

This candidate root is intentionally staged. Treat each phase prompt as the current task, but persist
state so a later worker session can resume from files.

The only durable delivery artifacts you may edit outside `workspace/` are:

- `delivery-state.json`
- `review-response.json`
- `closure.json`

Do not edit `inputs/`, `oracle/`, `verifiers/`, stale docs, legacy code, UI files, or protected
neighboring package files.
