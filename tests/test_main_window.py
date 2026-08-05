from PySide6.QtWidgets import QLabel, QToolBar

from scheme_builder.ui.main_window import create_main_window


def test_main_window_has_expected_title(qtbot):
    window = create_main_window()
    qtbot.addWidget(window)

    assert window.windowTitle() == "Scheme Builder"


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
