# Expected Regressions

The seeded report should converge on this evidence-backed read:

1. `blocking` modal focus escape
   Reverse-tab from `cancelButton` leaves the dialog and lands on `openLogFolderButton` while
   `advancedOptionsGroup` is collapsed. This breaks modal focus containment.
2. `major` high-DPI footer clipping
   At `150%` scaling, `previewSummaryLabel` and `footerRow` no longer fit together without overlap
   or clipping.
3. `major` dark-theme focus and selection loss
   In `Fusion Dark`, the selected row and focus frame for `baselineTable` become visually difficult
   to distinguish from the surrounding surface.

Expected stable controls:

- the forward tab order from `presetNameField` through `saveSnapshotButton` stays intact
- `Fusion Light` still renders a visible selected-row state for `baselineTable`

Expected gate decision:

- `REVISE`
