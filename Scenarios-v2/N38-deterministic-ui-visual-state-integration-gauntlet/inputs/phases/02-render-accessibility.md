# Phase 02 - Render Accessibility

Allowed edits for this phase:

- `candidate/workspace/src/console-view.mjs`
- `candidate/workspace/src/console.css`
- `candidate/workspace/implementation-ledger.json`

Repair rendered HTML and CSS state cues:

- Render a command palette with `role="listbox"` and `aria-activedescendant`.
- Render command options with stable ids, `role="option"`, `aria-selected`, `data-owner`, and
  `data-visible-return-cue`.
- Render visible return cue text for the active command.
- Render record tabs with `role="tablist"` and `role="tab"`.
- Render dirty, blocked-target, status, validation, and disabled save state as visible and
  machine-readable cues.
- Add stable ids for field errors and status by active record id.
- CSS must include `:focus-visible`, `min-inline-size`, `overflow-wrap`, `button[disabled]`,
  `[aria-selected="true"]`, and `@media (max-width: 480px)`.

Update the implementation ledger with phase id `02-render-accessibility`, owner
`frontend-engineer`, source id `S10`, and stale rejection of disabled-command focus advice.
