import sys

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow


def create_main_window() -> QMainWindow:
    window = QMainWindow()
    window.setWindowTitle("Scheme Builder")

    heading = QLabel("Редактор схем комплекса")
    heading.setObjectName("editorHeading")
    window.setCentralWidget(heading)

    return window


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = create_main_window()
    main_window.show()
    sys.exit(app.exec())
