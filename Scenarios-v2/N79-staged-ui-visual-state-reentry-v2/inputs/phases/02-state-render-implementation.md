# Phase 02: State And Render Implementation

Repair the state machine and accessible render output.

Allowed changes:

- `candidate/workspace/src/console-state.mjs`
- `candidate/workspace/src/console-view.mjs`
- `candidate/workspace/src/console.css`
- `candidate/workspace/tests/console-contract.test.mjs`
- `candidate/workspace/implementation-ledger.json`

Requirements:

- Disabled commands are skipped by focus and cannot be selected.
- Duplicate command ids must be disambiguated by owner/group key.
- Dirty state must be tracked per record against that record baseline.
- Dirty navigation must store the blocked target and visible return cue.
- Invalid saves and failed saves must preserve dirty state and return focus to the right cue.
- Rendered HTML must expose roles, ids, ownership markers, visible return cues, dirty state, `aria-live`, `aria-invalid`, and `aria-describedby`.
- Extend the ledger with phase `02-state-render-implementation`.

Do not edit layout or raster code unless a direct state/render dependency requires it.
