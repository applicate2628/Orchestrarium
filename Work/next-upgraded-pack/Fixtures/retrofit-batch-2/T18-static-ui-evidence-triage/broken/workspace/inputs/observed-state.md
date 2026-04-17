# Captured non-browser state

- Expanded-state static capture shows the note panel starting at the top-left of the matrix container, overlapping the caption and the first review row instead of sitting below the expanded row.
- The issue persists even when the panel already has a high stacking value. Raising `z-index` further does not change the anchor point.
- Closed-state audit still finds the note subtree in keyboard order because the stylesheet forces a rendered layout even when the `hidden` attribute is present.
- The note currently announces itself as a modal dialog even though the intended interaction is a lightweight inline disclosure tied to one row.
- The note copy says it should replace the row ranking with a global UI winner, which conflicts with the screen summary and the ranking contract.
