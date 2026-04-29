# Theme Variance Notes

Environment:

- Qt `6.7.2`
- `Fusion Light` and `Fusion Dark`
- checks repeated at `100%` and `150%`

## Stable light-theme read

In `Fusion Light`, `baselineTable` shows a visible selected-row fill and a distinct focus frame.
The control remains visually legible after the refresh.

## Dark-theme regression

In `Fusion Dark`, the selected row in `baselineTable` blends into the dialog body and the focus
frame becomes effectively invisible.

Relevant review-target anchor:

- `inputs/review-target/export_snapshot_dialog.qss`
- `QTableView#baselineTable::item:selected` uses `#30343d`
- `QTableView#baselineTable:focus` uses `border: 1px solid #30343d`
- the surrounding dialog body is `#2f343f`, leaving the focus frame and selected row too close to
  the background

Interpretation boundary:

This is a theme-specific rendering regression. It is not a screen-reader, semantics, or
information-architecture issue.
