from copy import deepcopy

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QSpinBox,
)

from scheme_builder.agent_scheme import InvalidAgentSchemeError
from scheme_builder.join_scheme import InvalidJoinSchemeError
from scheme_builder.metric import InvalidMetricError
from scheme_builder.template import InvalidTemplateError

EDITOR_ERRORS = (
    InvalidMetricError, InvalidTemplateError, InvalidAgentSchemeError, InvalidJoinSchemeError,
)


class UnsavedChanges:
    def __init__(self, editor, fields, extra_state, save, reset):
        self.editor = editor
        self.fields = fields
        self.extra_state = extra_state
        self.save = save
        self.reset = reset
        self.busy = False
        self.mark_clean()

    def state(self):
        values = []
        for field in self.fields:
            if isinstance(field, QLineEdit):
                values.append(field.text())
            elif isinstance(field, QPlainTextEdit):
                values.append(field.toPlainText())
            elif isinstance(field, QComboBox):
                values.append(field.currentText())
            elif isinstance(field, QCheckBox):
                values.append(field.isChecked())
            elif isinstance(field, QSpinBox):
                values.append(field.value())
        return values, deepcopy(self.extra_state())

    def mark_clean(self):
        self.saved_state = self.state()

    def save_changes(self) -> bool:
        try:
            return bool(self.save())
        except EDITOR_ERRORS as error:
            QMessageBox.warning(self.editor, "Не удалось сохранить изменения", str(error))
            return False

    def confirm(self) -> bool:
        if self.busy or self.state() == self.saved_state:
            return True
        box = QMessageBox(self.editor)
        box.setWindowTitle("Несохранённые изменения")
        box.setText("Сохранить изменения перед продолжением?")
        box.setIcon(QMessageBox.Icon.Warning)
        buttons = QMessageBox.StandardButton
        box.setStandardButtons(buttons.Save | buttons.Discard | buttons.Cancel)
        box.button(buttons.Save).setText("Сохранить")
        box.button(buttons.Discard).setText("Не сохранять")
        box.button(buttons.Cancel).setText("Отмена")
        box.setDefaultButton(buttons.Cancel)
        box.setEscapeButton(buttons.Cancel)
        answer = box.exec()
        self.busy = True
        try:
            if answer == buttons.Save:
                return self.save_changes()
            if answer == buttons.Discard:
                self.reset()
                self.mark_clean()
                return True
            return False
        except EDITOR_ERRORS as error:
            QMessageBox.warning(self.editor, "Не удалось продолжить", str(error))
            return False
        finally:
            self.busy = False

    def run(self, action) -> bool:
        if not self.confirm():
            return False
        try:
            action()
            return True
        except EDITOR_ERRORS as error:
            QMessageBox.warning(self.editor, "Не удалось выполнить действие", str(error))
            return False

    def select(self, catalog, current, previous, load):
        if self.busy:
            self.editor.delete_button.setEnabled(current is not None)
            if current is not None:
                load(str(current.data(Qt.ItemDataRole.UserRole)))
            return
        target = current.data(Qt.ItemDataRole.UserRole) if current else None
        with QSignalBlocker(catalog):
            if previous is None:
                catalog.setCurrentRow(-1)
            else:
                catalog.setCurrentItem(previous)
        if not self.confirm():
            return
        with QSignalBlocker(catalog):
            catalog.setCurrentRow(-1)
            for row in range(catalog.count()):
                if catalog.item(row).data(Qt.ItemDataRole.UserRole) == target:
                    catalog.setCurrentRow(row)
                    break
        if target is not None:
            load(str(target))
        self.editor.delete_button.setEnabled(target is not None)
