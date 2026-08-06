from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QLabel, QMainWindow, QToolBar

from scheme_builder.project import create_project
from scheme_builder.ui.create_project_dialog import CreateProjectDialog

DEFAULT_WINDOW_SIZE = QSize(1100, 700)
MINIMUM_WINDOW_SIZE = QSize(800, 500)
DEFAULT_PROJECTS_DIRECTORY = Path(__file__).resolve().parents[2] / "complexes"


def create_main_window(projects_directory: Path | None = None) -> QMainWindow:
    if projects_directory is None:
        projects_directory = DEFAULT_PROJECTS_DIRECTORY

    window = QMainWindow()
    window.setWindowTitle("Scheme Builder")
    window.resize(DEFAULT_WINDOW_SIZE)
    window.setMinimumSize(MINIMUM_WINDOW_SIZE)

    project_toolbar = QToolBar("Проект", window)
    project_toolbar.setObjectName("projectToolBar")

    create_project_action = QAction("Создать комплекс", window)
    create_project_action.setObjectName("createProjectAction")
    project_toolbar.addAction(create_project_action)

    open_project_action = QAction("Открыть комплекс", window)
    open_project_action.setObjectName("openProjectAction")
    project_toolbar.addAction(open_project_action)
    window.addToolBar(project_toolbar)

    empty_project_label = QLabel("Комплекс не открыт")
    empty_project_label.setObjectName("emptyProjectLabel")
    empty_project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.setCentralWidget(empty_project_label)

    create_project_action.triggered.connect(
        lambda checked=False: _show_create_project_dialog(
            window,
            projects_directory,
            empty_project_label,
        )
    )
    return window


def _show_create_project_dialog(
    window: QMainWindow,
    projects_directory: Path,
    project_label: QLabel,
) -> None:
    dialog = CreateProjectDialog(projects_directory, window)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    project_path = create_project(projects_directory, dialog.project_name)
    project_label.setText(f"Открыт комплекс: {project_path.name}")
