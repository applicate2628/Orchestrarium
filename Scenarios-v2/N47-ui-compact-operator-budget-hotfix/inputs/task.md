# Task

You are acting as `$frontend-engineer` on a bounded UI immutable-test hotfix bundle.

## Goal

Repair the editor state and rendering logic in `candidate/workspace/` so dirty form state,
navigation guards, validation, save/discard behavior, focus return, and accessibility status output
remain coherent across item switches and failed saves.

This is a compact UI hotfix lane. The runner transcript is part of the artifact budget:
`../meta/worker-output.txt` must stay at or below `40000` bytes. Use the copied bundle as the source
of truth, keep exploration narrow, avoid broad scans, and do not generate long explanatory output.

## Required output

Update only the editable production implementation files listed in `scenario.yaml`.
`candidate/workspace/tests/editor-contract.test.mjs` is fixed CI input and must not be edited.

The operator-budget gate will fail the run if the benchmark worker transcript exceeds the declared
`40000` byte budget. This is a scoreable requirement for this lane, not a post-run style preference.

## Required behavior

- dirty state must be tracked against each item's own baseline, not only the visible panel
- switching tabs/routes away from a dirty item must be blocked unless the caller confirms discard
- blocked navigation must preserve the target route as a visible decision cue
- invalid title or slug values must block save and keep the current draft dirty
- validation failure must mark the first invalid field and return focus to it
- failed saves must keep dirty state, preserve the previous baseline, and show an error status
- successful saves must commit the current draft as the new baseline, clear dirty state, and show success status
- discard must restore the active item's own baseline, not a stale global baseline
- rendered markup must expose a stable status id, `aria-live`, `aria-invalid`, `aria-describedby`,
  clean/dirty disabled states, and visible blocked-navigation/status cues
- CSS must include focus-visible styling, stable inline sizing, disabled styling, and safe text wrapping

## Disallowed behavior

- do not edit protected docs or `protected-copy.mjs`
- do not edit `candidate/workspace/tests/editor-contract.test.mjs`
- do not create a new framework or dependency
- do not hardcode one item id, one route, or one field value as a special case
- do not replace keyboard/form behavior with a mouse-only path
