from pathlib import Path

from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.ui.metric_editor import MetricEditor


class ProjectWorkspace(QWidget):
    def __init__(
        self,
        project_path: Path,
        project_name: str,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        project_label = QLabel(f"Открыт комплекс: {project_name}", self)
        project_label.setObjectName("projectNameLabel")

        metric_editor = MetricEditor(project_path, self)

        layout = QVBoxLayout(self)
        layout.addWidget(project_label)
        layout.addWidget(metric_editor, 1)
