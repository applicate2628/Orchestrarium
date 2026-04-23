# Phase 01 - State Machine

Allowed edits for this phase:

- `candidate/workspace/src/console-state.mjs`
- `candidate/workspace/implementation-ledger.json`

Repair the command and record state model:

- Use a stable command key that combines `group` and `id`.
- Skip disabled commands during keyboard movement and filtering.
- Block selection of disabled commands.
- Preserve an active command only when the exact command remains visible and enabled.
- Track dirty state per record against that record's own baseline.
- Block navigation away from a dirty active record unless the caller passes an explicit discard
  confirmation option.
- Store blocked target id and a visible return cue.
- Keep validation failures and failed saves dirty, with the previous baseline intact.
- Commit only the active record on successful save.
- Return focus to the first invalid field, the active status cue after save, and the active title
  field after discard.

Update the implementation ledger with phase id `01-state-machine`, owner `frontend-engineer`, and
source ids `S1` through `S9`.
