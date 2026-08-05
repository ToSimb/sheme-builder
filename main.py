import sys

from PySide6.QtWidgets import QApplication

from scheme_builder.ui.main_window import create_main_window


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_window = create_main_window()
    main_window.show()
    sys.exit(app.exec())
