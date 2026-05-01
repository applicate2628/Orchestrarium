Role: `$architect`

Goal: Produce an ordinary source-ranked ADR decision package for the PlanBridge migration.

Read only the approved source package in `inputs/`:

- `current-code-contract.md`
- `runtime-evidence.md`
- `downstream-constraints.md`
- `proposal-packet.md`
- `stale-adr.md`

Allowed edits:

- `candidate/adr-decision.json`
- `candidate/adr-decision.md`

Do not edit `inputs/`, `oracle/`, `verifiers/`, `scenario.yaml`, `README.md`, or
`candidate/README.md`.

Required decision:

- Choose one architecture path for the migration.
- Rank the source authority explicitly.
- Reject the unsafe alternatives explicitly.
- Preserve compatibility and rollback semantics.
- Include a non-claim ledger for stale or unsupported claims.

Expected JSON artifact:

- Write `candidate/adr-decision.json`.
- It must be valid JSON.
- It must contain the exact top-level keys required by the oracle.

Expected Markdown artifact:

- Write `candidate/adr-decision.md`.
- It must be a human-readable ADR summary derived from the same JSON decision.
- It must not introduce claims absent from the source package.

Scoreability:

- Wrapper/runtime/quota failures are `NOT-RUN`.
- A wrapper-success output that fails the verifier is a scoreable model `FAIL`.
