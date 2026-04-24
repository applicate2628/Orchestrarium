# Accessibility Notes

- Status text must be rendered in a stable live region so validation and save outcomes are announced.
- Invalid fields need both `aria-invalid="true"` and `aria-describedby` pointing at visible error text.
- Focus should return to the first invalid field after validation, and to the status cue after a
  successful save.
- Disabled controls must remain visually distinct and not resize the toolbar.
