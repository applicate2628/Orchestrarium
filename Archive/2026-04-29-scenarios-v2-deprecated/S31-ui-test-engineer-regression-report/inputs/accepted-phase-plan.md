# Accepted Phase Plan Excerpt

The reviewed phase is an additive visual refresh of the export dialog footer and preview summary.
The implementation lane is already complete; this review bundle covers only the desktop UI
regression gate for the modal dialog surface.

## Required UI checks

1. Opening the dialog places focus on `presetNameField`.
2. `Tab` and `Shift+Tab` keep focus inside the modal while `advancedOptionsGroup` is collapsed.
3. At `100%` and `150%` Windows scaling, `previewSummaryLabel`, `saveSnapshotButton`, and
   `cancelButton` remain fully visible with no clipping or overlap.
4. In `Fusion Light` and `Fusion Dark`, `baselineTable` keeps a visible focus frame and a clearly
   distinct selected-row state.
5. Stable controls such as `browseFolderButton` and the forward tab path from the name field
   through the footer must keep their pre-refresh behavior.

## Review output expectation

The reviewer returns a scoped UI test report. This phase does not ask for a bug triage table,
overall release sign-off, accessibility-only findings, or a redesign packet.
