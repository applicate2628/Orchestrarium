from __future__ import annotations


class Qt:
    NoFocus = 0
    TabFocus = 1
    StrongFocus = 2

    Key_Return = "Return"
    Key_Enter = "Enter"
    Key_Escape = "Escape"


class Signal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args, **kwargs):
        for callback in list(self._callbacks):
            callback(*args, **kwargs)


class QWidget:
    def __init__(self, object_name: str):
        self._object_name = object_name
        self._focus_policy = Qt.StrongFocus
        self._enabled = True
        self._visible = True
        self._dialog = None

    def objectName(self):
        return self._object_name

    def setFocusPolicy(self, policy):
        self._focus_policy = policy

    def focusPolicy(self):
        return self._focus_policy

    def setEnabled(self, enabled):
        self._enabled = bool(enabled)

    def isEnabled(self):
        return self._enabled

    def setVisible(self, visible):
        self._visible = bool(visible)

    def isVisible(self):
        return self._visible

    def setDialog(self, dialog):
        self._dialog = dialog

    def setFocus(self):
        if self._dialog is not None and self._enabled and self._focus_policy != Qt.NoFocus:
            self._dialog._focus_widget = self


class QLabel(QWidget):
    def __init__(self, object_name: str):
        super().__init__(object_name)
        self._text = ""
        self.setFocusPolicy(Qt.NoFocus)

    def setText(self, text):
        self._text = text

    def text(self):
        return self._text


class QLineEdit(QWidget):
    def __init__(self, object_name: str):
        super().__init__(object_name)
        self._text = ""
        self.textChanged = Signal()

    def setText(self, text):
        self._text = text
        self.textChanged.emit(text)

    def text(self):
        return self._text


class QCheckBox(QWidget):
    def __init__(self, object_name: str):
        super().__init__(object_name)
        self._checked = False

    def setChecked(self, checked):
        self._checked = bool(checked)

    def isChecked(self):
        return self._checked


class QPushButton(QWidget):
    def __init__(self, object_name: str, text: str):
        super().__init__(object_name)
        self._text = text
        self.clicked = Signal()

    def text(self):
        return self._text

    def click(self):
        if self.isEnabled():
            self.clicked.emit()


class QDialog(QWidget):
    def __init__(self, object_name: str):
        super().__init__(object_name)
        self._focus_widget = None
        self._tab_order = {}
        self.accepted = False
        self.rejected = False

    def register_widget(self, widget):
        widget.setDialog(self)

    def setTabOrder(self, first, second):
        self._tab_order[first] = second

    def tab_successor(self, widget):
        return self._tab_order.get(widget)

    def focusWidget(self):
        return self._focus_widget

    def accept(self):
        self.accepted = True
        self.rejected = False

    def reject(self):
        self.rejected = True
        self.accepted = False

    def reset_result(self):
        self.accepted = False
        self.rejected = False


class QDialogButtonBox(QWidget):
    Ok = "ok"
    Cancel = "cancel"

    def __init__(self, object_name: str = "buttons"):
        super().__init__(object_name)
        self._buttons = {
            self.Ok: QPushButton("save_button", "Save"),
            self.Cancel: QPushButton("cancel_button", "Cancel"),
        }

    def button(self, role):
        return self._buttons[role]


class QKeyEvent:
    def __init__(self, key):
        self._key = key

    def key(self):
        return self._key
