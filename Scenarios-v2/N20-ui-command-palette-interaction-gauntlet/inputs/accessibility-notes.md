# Accessibility Notes

The command palette is a listbox-like interaction. The active option must be surfaced through
`aria-activedescendant`, while each visible action needs `role="option"` and an `aria-selected`
value. The visible return cue is user-facing state, not only a hidden data attribute.
