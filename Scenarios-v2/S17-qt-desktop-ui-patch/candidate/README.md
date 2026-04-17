# Candidate Root

This is the mutable run root copied for each scored execution.

The start state is intentionally wrong for desktop keyboard use. The dialog in
`qt-settings-dialog/` mis-declares focus policy, uses the wrong tab order, accepts invalid `Return`
presses, and mishandles dialog reuse after a prior result.

## Editable files

- `qt-settings-dialog/src/qt_settings_dialog/rename_preset_dialog.py`
- `qt-settings-dialog/tests/test_rename_preset_dialog.py`

## Read-only context inside the candidate root

- `qt-settings-dialog/README.md`
- `qt-settings-dialog/src/qt_settings_dialog/__init__.py`
- `qt-settings-dialog/src/qt_settings_dialog/qt_compat.py`

The intended repair path is to keep the change inside the dialog seam and its direct verification
file only.
