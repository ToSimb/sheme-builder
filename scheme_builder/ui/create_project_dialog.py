from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)


class CreateProjectDialog(QDialog):
    def __init__(self, projects_directory: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("createProjectDialog")
        self.setWindowTitle("Создать комплекс")

        layout = QFormLayout(self)

        self._name_edit = QLineEdit()
        self._name_edit.setObjectName("projectNameEdit")
        layout.addRow("Название комплекса:", self._name_edit)

        directory_label = QLabel(str(projects_directory))
        directory_label.setObjectName("projectsDirectoryLabel")
        layout.addRow("Папка:", directory_label)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        create_button = button_box.button(QDialogButtonBox.StandardButton.Ok)
        create_button.setObjectName("createProjectButton")
        create_button.setText("Создать")
        create_button.setEnabled(False)
        button_box.button(QDialogButtonBox.StandardButton.Cancel).setText("Отмена")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

        self._name_edit.textChanged.connect(
            lambda text: create_button.setEnabled(bool(text.strip()))
        )

    @property
    def project_name(self) -> str:
        return self._name_edit.text().strip()
