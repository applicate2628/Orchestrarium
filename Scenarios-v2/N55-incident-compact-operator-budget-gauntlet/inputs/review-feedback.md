# Review Feedback

Accepted review comments:

| ID | Comment | Required response |
|---|---|---|
| `R1` | Public API compatibility is protected. | Do not edit `api.py`, `__init__.py`, or `models.py`. |
| `R2` | The failure is in the deploy runtime, not documentation, legacy helpers, or UI badges. | Keep docs, legacy, and UI files unchanged. |
| `R3` | The incident commander needs causal source trace. | Preserve request `source` in audit and report state. |
| `R4` | The fix must be retry-safe. | Repeated runs and crash resume must not replay committed side effects. |
| `R5` | Validation evidence must be explicit. | Update tests or explain which direct tests/checks cover the repair in the reconciliation note. |
