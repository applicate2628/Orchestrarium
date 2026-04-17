from __future__ import annotations

import sys
from pathlib import Path


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from qt_settings_dialog import Qt, RenamePresetDialog


def tab_chain(dialog, steps=4):
    chain = []
    current = dialog.name_edit
    seen = set()
    while current is not None and current not in seen and len(chain) < steps:
        chain.append(current.objectName())
        seen.add(current)
        current = dialog.tab_successor(current)
    return chain


def test_focus_chain_and_error_label_policy():
    dialog = RenamePresetDialog()
    assert dialog.focusWidget().objectName() == "name_edit", "dialog should start on the name field"
    assert dialog.error_label.focusPolicy() == Qt.NoFocus, "error label should never be focusable"
    assert tab_chain(dialog) == [
        "name_edit",
        "pin_checkbox",
        "save_button",
        "cancel_button",
    ], "desktop tab order is incorrect"


def test_blank_name_recovers_focus_and_blocks_return_accept():
    dialog = RenamePresetDialog()
    dialog.save_button.setFocus()
    dialog.name_edit.setText("   ")

    assert not dialog.save_button.isEnabled(), "blank name should disable Save"
    assert dialog.error_label.isVisible(), "blank name should show the validation label"
    assert dialog.focusWidget().objectName() == "name_edit", "focus should recover to the name field"

    dialog.reset_result()
    dialog.name_edit.setFocus()
    dialog.press_key(Qt.Key_Return)
    assert not dialog.accepted, "Return should not accept while the dialog is invalid"
    assert not dialog.rejected, "invalid Return should not reject the dialog"


def test_escape_and_reopen_reset_dialog_state():
    dialog = RenamePresetDialog()
    dialog.press_key(Qt.Key_Escape)
    assert dialog.rejected, "Escape should reject the dialog"

    dialog.prepare_for_reopen("Weekend Plan")
    assert not dialog.accepted and not dialog.rejected, "reopen should clear prior result state"
    assert dialog.focusWidget().objectName() == "name_edit", "reopen should restore focus to name_edit"
    assert dialog.save_button.isEnabled(), "valid reopen name should keep Save enabled"
    assert not dialog.error_label.isVisible(), "reopen with a valid name should clear stale errors"


def main():
    failures = []
    for test in (
        test_focus_chain_and_error_label_policy,
        test_blank_name_recovers_focus_and_blocks_return_accept,
        test_escape_and_reopen_reset_dialog_state,
    ):
        try:
            test()
        except AssertionError as exc:
            failures.append(f"{test.__name__}: {exc}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print("qt-settings-dialog tests PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
