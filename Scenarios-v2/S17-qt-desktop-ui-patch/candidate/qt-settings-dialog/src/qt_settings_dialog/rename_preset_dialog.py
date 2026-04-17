from __future__ import annotations

from .qt_compat import Qt, QCheckBox, QDialog, QDialogButtonBox, QKeyEvent, QLabel, QLineEdit


def normalize_preset_name(text: str) -> str:
    return " ".join(text.split())


class RenamePresetDialog(QDialog):
    def __init__(self, suggested_name: str = "Morning Focus"):
        super().__init__("rename_preset_dialog")
        self.name_edit = QLineEdit("name_edit")
        self.pin_checkbox = QCheckBox("pin_checkbox")
        self.error_label = QLabel("error_label")
        self.buttons = QDialogButtonBox()
        self.save_button = self.buttons.button(QDialogButtonBox.Ok)
        self.cancel_button = self.buttons.button(QDialogButtonBox.Cancel)

        for widget in (
            self.name_edit,
            self.pin_checkbox,
            self.error_label,
            self.buttons,
            self.save_button,
            self.cancel_button,
        ):
            self.register_widget(widget)

        self.name_edit.textChanged.connect(self._on_name_changed)
        self.save_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        self.error_label.setVisible(False)
        self.error_label.setFocusPolicy(Qt.StrongFocus)

        self.setTabOrder(self.name_edit, self.cancel_button)
        self.setTabOrder(self.cancel_button, self.pin_checkbox)
        self.setTabOrder(self.pin_checkbox, self.save_button)

        self.name_edit.setText(suggested_name)
        self.name_edit.setFocus()

    def _on_name_changed(self, text: str):
        is_valid = bool(normalize_preset_name(text))
        self.save_button.setEnabled(is_valid)
        if is_valid:
            self.error_label.setText("")
            self.error_label.setVisible(False)
            return

        self.error_label.setText("Preset name is required")
        self.error_label.setVisible(True)

    def press_key(self, key):
        self.keyPressEvent(QKeyEvent(key))

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.accept()
            return
        if event.key() == Qt.Key_Escape:
            self.reject()

    def prepare_for_reopen(self, suggested_name: str):
        self.name_edit.setText(suggested_name)
        if self.save_button.isEnabled():
            self.save_button.setFocus()
        else:
            self.cancel_button.setFocus()
