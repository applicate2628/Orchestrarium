# Verifiers

Commands:

- `python verifiers/check_incident_integration_repair.py --bundle-shape-only`
- `python verifiers/check_incident_integration_repair.py --expect-start-state`
- `python verifiers/check_incident_integration_repair.py`
- `python verifiers/check_scope.py --changed-path <path>`

The main verifier checks bundle shape, start-state failure IDs, runtime integration behavior, and
the required `candidate/reconciliation-note.md` source arbitration checks.
