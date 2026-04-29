# Runtime Probe Cases

Use these IDs in `runtimeEvidence.caseId` and `witnessMatrix`.

Runtime failure probes:

- `R1`: source conflict with owner present and regression passed.
- `R2`: pending regression proof with owner present and source fresh.
- `R3`: source conflict combined with missing owner.
- `R4`: disabled publish state on mobile action order.
- `R5`: auditor export for a record with owner-only notes and internal resolution notes.
- `R6`: text-only follow-up diff after an existing publish receipt.
- `R7`: owner-remediation return focus after adding an owner.

Benign probes:

- `B1`: disabled publish opacity plus visible disabled reason.
- `B2`: docs link with `rel="noopener"`.
- `B3`: empty draft label zero-state cue.
