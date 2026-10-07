from pathlib import Path

from PySide6.QtCore import QSignalBlocker
from PySide6.QtWidgets import (
    QLabel,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.ui.agent_scheme_editor import AgentSchemeEditor
from scheme_builder.ui.join_scheme_editor import JoinSchemeEditor
from scheme_builder.ui.metric_editor import MetricEditor
from scheme_builder.ui.template_editor import TemplateEditor
from scheme_builder.ui.unsaved_changes import EDITOR_ERRORS


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
        self.agent_scheme_editor = AgentSchemeEditor(project_path, self)
        self.join_scheme_editor = JoinSchemeEditor(project_path, self)

        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("projectTabs")
        self.tabs.addTab(self.metric_editor, "Метрики")
        self.tabs.addTab(self.template_editor, "Шаблоны")
        self.tabs.addTab(self.agent_scheme_editor, "AgentScheme")
        self.tabs.addTab(self.join_scheme_editor, "JoinScheme")
        self._active_tab = self.tabs.currentIndex()
        self.tabs.currentChanged.connect(self._refresh_current_tab)

        layout = QVBoxLayout(self)
        layout.addWidget(project_label)
        layout.addWidget(self.tabs, 1)

    def confirm_leave(self) -> bool:
        return self.tabs.widget(self._active_tab).unsaved.confirm()

    def _refresh_current_tab(self, index: int) -> None:
        if index < 0 or index == self._active_tab:
            return
        with QSignalBlocker(self.tabs):
            self.tabs.setCurrentIndex(self._active_tab)
        if not self.confirm_leave():
            return
        try:
            if index == 0:
                self.metric_editor.refresh_usage()
            elif index == 1:
                self.template_editor.refresh()
            elif index == 2:
                self.agent_scheme_editor.refresh()
            elif index == 3:
                self.join_scheme_editor.refresh()
        except EDITOR_ERRORS as error:
            QMessageBox.warning(self, "Не удалось обновить вкладку", str(error))
            return
        with QSignalBlocker(self.tabs):
            self.tabs.setCurrentIndex(index)
        self._active_tab = index
