# Keyboard And Focus Run

Environment:

- Windows 11 desktop shell
- Qt `6.7.2`
- `Fusion Light`
- `100%` scaling unless noted otherwise

## Stable control check

Forward tab order remained stable on the first pass:

`presetNameField -> includeNotesCheckbox -> baselineTable -> browseFolderButton -> saveSnapshotButton -> cancelButton`

This stable sequence matches the expected control path in `inputs/accepted-phase-plan.md` and shows
that the regression is not a full dialog-wide focus collapse.

## Regression repro

1. Open the export dialog with `advancedOptionsGroup` collapsed.
2. Press `Tab` until `cancelButton` holds focus.
3. Press `Shift+Tab`.

Observed result:

- focus leaves the modal and lands on `openLogFolderButton` in the parent window toolbar
- the toolbar focus indicator appears behind the modal instead of returning to
  `saveSnapshotButton` or `browseFolderButton`
- the issue reproduces at both `100%` and `150%` scaling

Relevant review-target anchor:

- `inputs/review-target/export_snapshot_dialog.py`
- the `focusNextPrevChild` override redirects reverse-tab from `cancelButton` to
  `openLogFolderButton` when `advancedOptionsGroup` is hidden
