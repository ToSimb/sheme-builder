from PySide6.QtGui import QBrush, QColor

SUCCESS_COLOR = "#d1e7dd"
WARNING_COLOR = "#fff3cd"
DANGER_COLOR = "#f8d7da"
SUCCESS_TEXT_COLOR = "#146c43"
WARNING_TEXT_COLOR = "#856404"
DANGER_TEXT_COLOR = "#c62828"

SUCCESS_BRUSH = QBrush(QColor(SUCCESS_COLOR))
WARNING_BRUSH = QBrush(QColor(WARNING_COLOR))
DANGER_BRUSH = QBrush(QColor(DANGER_COLOR))


def background_style(color: str | None) -> str:
    return "" if color is None else f"background-color: {color};"
