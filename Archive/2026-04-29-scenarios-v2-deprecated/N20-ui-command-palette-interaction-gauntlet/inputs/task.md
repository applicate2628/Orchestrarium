# Task

You are acting as `$frontend-engineer` on a bounded UI implementation bundle.

## Goal

Repair the command palette state and rendering logic in `candidate/workspace/` so keyboard
navigation, filtering, focus recovery, disabled actions, ARIA state, and visible return cues stay
coherent.

## Required behavior

- Arrow navigation wraps through visible enabled actions only.
- Disabled actions cannot become active and cannot be selected.
- Filtering preserves the previous active item when it remains visible and enabled.
- Filtering moves to the first visible enabled action when the previous active item disappears.
- `Escape` clears the filter and restores the last stable active action.
- Rendered markup exposes a `role="listbox"` root with `aria-activedescendant`.
- Each visible action renders a stable option id, `role="option"`, `aria-selected`, `data-owner`,
  and `data-visible-return-cue`.
- The active option must include visible return cue text for where focus will return.
- CSS must include focus-visible styling and stable width/text wrapping constraints.

## Disallowed behavior

- do not edit protected docs or `protected-copy.mjs`
- do not create a new framework or dependency
- do not hardcode one test query or one action id as a special case
- do not replace keyboard behavior with a mouse-only path
