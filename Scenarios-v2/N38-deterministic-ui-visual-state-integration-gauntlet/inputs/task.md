# Task

You are acting as `$frontend-engineer` on a staged UI implementation bundle.

## Goal

Repair the incident review console in `candidate/workspace/` so command focus, dirty record
state, guarded navigation, validation/focus return, accessible markup, responsive layout, and
deterministic raster preview remain coherent across fresh staged invocations.

## Global behavior

- Disabled commands must be skipped by keyboard focus and cannot be selected.
- Commands are identified by both group and id because the same id can appear under different
  owners.
- Filtering must preserve the current active command only when that exact command remains visible
  and enabled; otherwise it moves to the first visible enabled command.
- Dirty state is tracked per record against that record's own baseline.
- Navigation away from a dirty record is blocked unless the caller explicitly confirms discard.
- Blocked navigation stores the requested target and a visible return cue.
- Invalid title or slug values block save, preserve dirty state, and focus the first invalid field.
- Failed saves preserve dirty state and the previous baseline.
- Successful saves commit only the active record, clear its dirty state, and focus the status cue.
- Rendered HTML must expose stable roles, ids, ownership markers, visible return cues, `aria-live`,
  `aria-invalid`, `aria-describedby`, and disabled/dirty state.
- `computeLayout()` must return deterministic boxes that fit 320, 768, and 1280 width viewports
  without overlapping interactive targets.
- `renderRaster()` must preserve transparent gaps, draw alert/selection overlays after base cells,
  keep the legend zero-centered, and export a valid ASCII `P3` PPM.

## Disallowed behavior

- Do not edit protected docs, stale notes, `protected-copy.mjs`, inputs, oracle, or verifiers.
- Do not create a new UI framework, browser dependency, or image dependency.
- Do not hardcode one visible test case, one record id, one command id, or one expected frame.
- Do not replace keyboard/form behavior with mouse-only behavior.
- Do not use negative letter spacing or absolute positioning to force layout.
