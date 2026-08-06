from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QListWidget,
    QSplitter,
    QTabWidget,
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

        tabs = QTabWidget(self)
        tabs.setObjectName("projectTabs")
        tabs.addTab(self._create_template_tab(), "Шаблоны")
        tabs.addTab(MetricEditor(project_path, tabs), "Метрики")
        tabs.setCurrentIndex(1)

        layout = QVBoxLayout(self)
        layout.addWidget(project_label)
        layout.addWidget(tabs)

    @staticmethod
    def _create_template_tab() -> QWidget:
        tab = QWidget()
        splitter = QSplitter(Qt.Orientation.Horizontal, tab)

        template_list = QListWidget(splitter)
        template_list.setObjectName("templateList")
        empty_editor = QLabel("Редактор шаблонов будет добавлен следующим этапом.", splitter)
        empty_editor.setAlignment(Qt.AlignmentFlag.AlignCenter)

        splitter.addWidget(template_list)
        splitter.addWidget(empty_editor)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(tab)
        layout.addWidget(splitter)
        return tab
