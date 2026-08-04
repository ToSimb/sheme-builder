from PySide6.QtWidgets import QLabel

from main import create_main_window


def test_main_window_has_expected_title(qtbot):
    window = create_main_window()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Scheme Builder"


def test_main_window_shows_editor_heading(qtbot):
    window = create_main_window()
    qtbot.addWidget(window)

    heading = window.findChild(QLabel, "editorHeading")

    assert heading is not None
    assert heading.text() == "Редактор схем комплекса"
