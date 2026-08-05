from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QToolBar,
)


def create_main_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("Scheme Builder")

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
