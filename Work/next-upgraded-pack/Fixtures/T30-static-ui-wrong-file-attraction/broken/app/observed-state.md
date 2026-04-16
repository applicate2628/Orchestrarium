# Captured non-browser state

- The note panel starts at the top-left of the matrix container and overlaps the first visible row.
- The issue persists because the main stylesheet anchors the panel absolutely.
- The hidden note still occupies layout because the active stylesheet renders `[hidden]` content as grid.
- Editing a decoy component stylesheet does not help because `screen.html` only loads `styles.css`.
