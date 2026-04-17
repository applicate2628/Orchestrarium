# Interaction contract

- The provider-local note is an inline supporting disclosure for the selected row, not a global modal.
- When expanded, the note must stay visually attached to the selected row and should appear below that row instead of covering the table header or earlier rows.
- Closed state must remove the note from keyboard order and assistive-technology reading order.
- Focus should stay understandable for keyboard users: the trigger opens the note, the note can be dismissed, and dismissal should not strand focus.
- The row ranking remains the primary routing signal. A provider-local note may narrow a row or add caveats, but it must not overwrite the row order with a global winner claim.
- The next admitted fix should stay local to the markup and styles in this screen. Do not redesign the whole screen into cards or a different navigation model.
