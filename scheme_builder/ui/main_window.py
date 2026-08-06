from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QToolBar,
)

from scheme_builder.project import InvalidProjectError, create_project, open_project
from scheme_builder.ui.create_project_dialog import CreateProjectDialog
from scheme_builder.ui.project_workspace import ProjectWorkspace

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
        )
    )
    open_project_action.triggered.connect(
        lambda checked=False: _show_open_project_dialog(
            window,
            projects_directory,
        )
    )
    return window


def _show_create_project_dialog(
    window: QMainWindow,
    projects_directory: Path,
) -> None:
    dialog = CreateProjectDialog(projects_directory, window)
    if dialog.exec() != QDialog.DialogCode.Accepted:
        return

    project_path = create_project(projects_directory, dialog.project_name)
    _show_project_workspace(window, project_path, project_path.name)


def _show_open_project_dialog(
    window: QMainWindow,
    projects_directory: Path,
) -> None:
    selected_directory = QFileDialog.getExistingDirectory(
        window,
        "Открыть комплекс",
        str(projects_directory),
    )
    if not selected_directory:
        return

    try:
        project_data = open_project(Path(selected_directory))
    except InvalidProjectError as error:
        QMessageBox.warning(window, "Не удалось открыть комплекс", str(error))
        return

    _show_project_workspace(
        window,
        Path(selected_directory),
        str(project_data["name"]),
    )


def _show_project_workspace(
    window: QMainWindow,
    project_path: Path,
    project_name: str,
) -> None:
    window.setCentralWidget(ProjectWorkspace(project_path, project_name, window))
