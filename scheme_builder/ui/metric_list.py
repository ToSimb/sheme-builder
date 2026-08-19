from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QListWidget


def apply_metric_group_stripes(metric_list: QListWidget) -> None:
    previous_group: str | None = None
    alternate = False
    palette = metric_list.palette()

    for row in range(metric_list.count()):
        item = metric_list.item(row)
        metric_id = str(item.data(Qt.ItemDataRole.UserRole))
        group = metric_id.partition(".")[0]
        if previous_group is not None and group != previous_group:
            alternate = not alternate
        previous_group = group
        role = (
            QPalette.ColorRole.AlternateBase
            if alternate
            else QPalette.ColorRole.Base
        )
        item.setBackground(palette.brush(role))
