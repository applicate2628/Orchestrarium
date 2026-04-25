# Task

Repair the ReleaseGate UI runtime behavior.

Allowed edits:

- `candidate/workspace/src/state.mjs`
- `candidate/workspace/src/view.mjs`
- `candidate/workspace/src/app.mjs`
- `candidate/workspace/src/styles.css`
- `candidate/ui-runtime-ledger.json`

Do not edit the visible verifier script, package metadata, README files, oracle files, verifier
files, or scenario metadata.

Required behavior:

- filter buttons must update visible cards and `aria-pressed`
- summary text must show `<visible> / <total> visible`
- hidden cards must remain in the DOM with `data-visible="false"`
- dirty toggles must work with click, `Enter`, and Space keydown
- dirty state must enable the save button and update the polite status text
- save must clear all dirty state, disable the save button, and report `All changes saved`
- source item data must not be mutated
- keep the implementation dependency-free
- update `ui-runtime-ledger.json` with exact changed files, event handling, keyboard behavior, dirty
  state, save behavior, payload immutability, and patch-quality notes

The visible check only covers initial render. Hidden verification dispatches events and checks runtime
state transitions.
