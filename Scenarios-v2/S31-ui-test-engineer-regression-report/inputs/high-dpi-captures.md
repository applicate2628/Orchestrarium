# High-DPI Capture Notes

Environment:

- Windows 11
- Qt `6.7.2`
- `Fusion Light`
- `3840x2160` display

## Control observation at `100%`

- `previewSummaryLabel` fits on two lines
- `saveSnapshotButton` and `cancelButton` render with full vertical padding
- `footerRow` stays visually separated from the summary body

## Regression observation at `150%`

- `previewSummaryLabel` wraps to a third line and overlaps the top edge of `footerRow`
- descenders in the `Save snapshot` label are clipped
- the bottom border of `cancelButton` is partially cut off

Relevant review-target anchor:

- `inputs/review-target/export_snapshot_dialog.ui`
- `footerRow` is fixed to `52` px in both directions
- `previewSummaryLabel` keeps a fixed maximum height even after the refresh increased text density

Interpretation boundary:

This is a layout regression tied to scaling behavior, not a copy or UX-structure issue.
