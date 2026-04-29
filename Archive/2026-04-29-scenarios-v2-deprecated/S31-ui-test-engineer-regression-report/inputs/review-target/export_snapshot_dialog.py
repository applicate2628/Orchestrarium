from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QPushButton, QWidget


class ExportSnapshotDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("exportSnapshotDialog")

        self.presetNameField = QWidget(self)
        self.presetNameField.setObjectName("presetNameField")

        self.includeNotesCheckbox = QWidget(self)
        self.includeNotesCheckbox.setObjectName("includeNotesCheckbox")

        self.baselineTable = QWidget(self)
        self.baselineTable.setObjectName("baselineTable")

        self.browseFolderButton = QPushButton("Browse...", self)
        self.browseFolderButton.setObjectName("browseFolderButton")

        self.saveSnapshotButton = QPushButton("Save snapshot", self)
        self.saveSnapshotButton.setObjectName("saveSnapshotButton")

        self.cancelButton = QPushButton("Cancel", self)
        self.cancelButton.setObjectName("cancelButton")

        self.advancedOptionsGroup = QWidget(self)
        self.advancedOptionsGroup.setObjectName("advancedOptionsGroup")
        self.advancedOptionsGroup.setVisible(False)

        self.openLogFolderButton = QPushButton("Open log folder", parent)
        self.openLogFolderButton.setObjectName("openLogFolderButton")

    def focusNextPrevChild(self, next_child):
        if (
            not next_child
            and self.focusWidget() is self.cancelButton
            and not self.advancedOptionsGroup.isVisible()
        ):
            self.openLogFolderButton.setFocus(Qt.BacktabFocusReason)
            return True
        return super().focusNextPrevChild(next_child)
