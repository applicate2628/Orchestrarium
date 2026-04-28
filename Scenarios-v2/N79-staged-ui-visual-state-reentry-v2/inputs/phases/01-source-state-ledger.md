# Phase 01: Source And State Ledger

Create the source-binding part of the reentry packet before changing code.

Allowed change:

- `candidate/workspace/implementation-ledger.json`

Requirements:

- Use `contractId: N79-staged-ui-visual-state-reentry-v2`.
- Use `planFingerprint: n79-staged-ui-visual-state-reentry-v2`.
- Add a phase entry `01-source-state-ledger`.
- Bind source ids `S1` through `S12` to the expected UI behavior.
- Explicitly reject `inputs/stale-visual-advice.md`.
- Preserve exact ownership terms: disabled destructive actions, one global dirty flag, neutral zero values, and desktop-only column.

Do not edit implementation files in this phase.
