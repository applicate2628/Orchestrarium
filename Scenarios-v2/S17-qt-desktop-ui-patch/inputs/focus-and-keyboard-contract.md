# Focus And Keyboard Contract

## Focus chain

The accepted desktop tab order is:

1. `name_edit`
2. `pin_checkbox`
3. `save_button`
4. `cancel_button`

The error label is status text only. It must never become a keyboard stop.

## Key handling

- `Return` or `Enter` should behave like an activate-`Save` shortcut only when the dialog has a
  valid non-empty normalized name
- `Escape` should reject the dialog from the current child context
- a validation failure should keep the user in the editable field instead of parking focus on a
  disabled action button

## Boundary note

This is a desktop keyboard contract for Qt Widgets. Do not translate it into browser tab-index
rules, DOM event listeners, or generic web accessibility fixes.
