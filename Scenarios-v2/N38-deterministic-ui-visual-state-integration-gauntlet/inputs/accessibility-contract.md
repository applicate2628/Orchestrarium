# Accessibility Contract

The rendered console must provide stable machine-readable and visible cues:

- command palette root: `role="listbox"` and `aria-activedescendant`
- command options: `role="option"`, `aria-selected`, `data-owner`,
  `data-visible-return-cue`
- record tabs: `role="tablist"` and `role="tab"` with selected and dirty markers
- detail form: stable field ids by record, invalid field state, and error description ids
- status cue: stable `status-<record id>` id and `aria-live="polite"`
- blocked navigation cue: target id and visible cue text
- disabled save button when the active record is clean
