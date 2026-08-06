from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QToolBar,
)

DEFAULT_WINDOW_SIZE = QSize(1100, 700)
MINIMUM_WINDOW_SIZE = QSize(800, 500)


def create_main_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("Scheme Builder")
    window.resize(DEFAULT_WINDOW_SIZE)
    window.setMinimumSize(MINIMUM_WINDOW_SIZE)

    project_toolbar = QToolBar("Проект", window)
    project_toolbar.setObjectName("projectToolBar")
    project_toolbar.addAction(QAction("Создать комплекс", window))
    project_toolbar.addAction(QAction("Открыть комплекс", window))
    window.addToolBar(project_toolbar)

    empty_project_label = QLabel("Комплекс не открыт")
    empty_project_label.setObjectName("emptyProjectLabel")
    empty_project_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    window.setCentralWidget(empty_project_label)
    return window
