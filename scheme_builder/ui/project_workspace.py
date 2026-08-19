from pathlib import Path

from PySide6.QtWidgets import (
    QLabel,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.ui.metric_editor import MetricEditor
from scheme_builder.ui.template_editor import TemplateEditor


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

        self.metric_editor = MetricEditor(project_path, self)
        self.template_editor = TemplateEditor(project_path, self)

        tabs = QTabWidget(self)
        tabs.setObjectName("projectTabs")
        tabs.addTab(self.metric_editor, "Метрики")
        tabs.addTab(self.template_editor, "Шаблоны")
        tabs.currentChanged.connect(self._refresh_current_tab)

        layout = QVBoxLayout(self)
        layout.addWidget(project_label)
        layout.addWidget(tabs, 1)

    def _refresh_current_tab(self, index: int) -> None:
        if index == 1:
            self.template_editor.refresh()
