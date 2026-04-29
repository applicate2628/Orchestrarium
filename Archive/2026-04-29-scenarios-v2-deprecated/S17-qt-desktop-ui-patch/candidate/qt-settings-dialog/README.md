# Qt Settings Dialog

This bundle-local candidate subtree models a tiny Qt Widgets rename flow using a local compatibility
layer so the benchmark can run without external GUI dependencies.

## Local layout

- `src/qt_settings_dialog/rename_preset_dialog.py` is the editable dialog module
- `src/qt_settings_dialog/qt_compat.py` is the read-only Qt-style harness used by the verifiers
- `tests/test_rename_preset_dialog.py` is the editable direct verification file

## Local validation

From this directory:

- run `python tests/test_rename_preset_dialog.py`

This candidate stays intentionally desktop-specific. There is no browser surface, no DOM, and no
model/view layer in this subtree.
