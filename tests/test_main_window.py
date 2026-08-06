from PySide6.QtCore import QSize, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QPushButton, QToolBar

from scheme_builder.ui.main_window import create_main_window


def test_main_window_has_expected_title(qtbot):
    window = create_main_window()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Scheme Builder"


def test_main_window_has_expected_size(qtbot):
    window = create_main_window()
    qtbot.addWidget(window)

    assert window.size() == QSize(1100, 700)
    assert window.minimumSize() == QSize(800, 500)


def test_main_window_has_project_toolbar(qtbot):
    window = create_main_window()
    qtbot.addWidget(window)

    toolbar = window.findChild(QToolBar, "projectToolBar")

    assert toolbar is not None
    assert [action.text() for action in toolbar.actions()] == [
        "Создать комплекс",
        "Открыть комплекс",
    ]


def test_main_window_shows_empty_project_state(qtbot):
    window = create_main_window()
    qtbot.addWidget(window)

    label = window.findChild(QLabel, "emptyProjectLabel")

    assert label is not None
    assert label.text() == "Комплекс не открыт"


def test_create_project_action_creates_project(qtbot, tmp_path):
    window = create_main_window(projects_directory=tmp_path)
    qtbot.addWidget(window)

    action = window.findChild(QAction, "createProjectAction")
    observed_dialog = {}

    def complete_dialog():
        dialog = window.findChild(QDialog, "createProjectDialog")
        name_edit = dialog.findChild(QLineEdit, "projectNameEdit")
        directory_label = dialog.findChild(QLabel, "projectsDirectoryLabel")
        create_button = dialog.findChild(QPushButton, "createProjectButton")

        observed_dialog["directory"] = directory_label.text()
        observed_dialog["button_text"] = create_button.text()
        name_edit.setText("demo-complex")
        dialog.accept()

    assert action is not None
    QTimer.singleShot(0, complete_dialog)
    action.trigger()

    assert observed_dialog == {
        "directory": str(tmp_path),
        "button_text": "Создать",
    }
    assert (tmp_path / "demo-complex" / "project.json").is_file()
    assert window.findChild(QLabel, "emptyProjectLabel").text() == (
        "Открыт комплекс: demo-complex"
    )
