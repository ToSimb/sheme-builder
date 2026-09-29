from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QListWidget


def apply_usage_marks(catalog: QListWidget, used_ids: set[str]) -> None:
    pixmap = QPixmap(16, 16)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#2eaf50"), 2.5))
    painter.drawLine(3, 8, 6, 11)
    painter.drawLine(6, 11, 13, 4)
    painter.end()
    icon = QIcon(pixmap)
    icon.addPixmap(pixmap, QIcon.Mode.Selected)
    for row in range(catalog.count()):
        item = catalog.item(row)
        item.setIcon(
            icon if item.data(Qt.ItemDataRole.UserRole) in used_ids else QIcon()
        )
