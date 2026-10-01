from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.agent_scheme import (
    InvalidAgentSchemeError,
    build_agent_tree,
    delete_agent_scheme,
    export_agent_scheme,
    load_agent_schemes,
    save_agent_scheme,
)
from scheme_builder.config import CATALOG_LIST_WIDTH
from scheme_builder.template import InvalidTemplateError, load_templates
from scheme_builder.ui.reference_status import MISSING_REFERENCE_BRUSH
from scheme_builder.ui.unsaved_changes import UnsavedChanges


class AgentSchemeEditor(QWidget):
    def __init__(self, project_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.project_path = project_path
        self.agent_schemes: dict[str, dict[str, object]] = {}
        self.templates: dict[str, dict[str, object]] = {}
        self.roots: list[dict[str, int | str]] = []

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        list_panel = QWidget(splitter)
        list_panel.setMinimumWidth(CATALOG_LIST_WIDTH)
        list_layout = QVBoxLayout(list_panel)
        self.agent_scheme_list = QListWidget(list_panel)
        self.agent_scheme_list.setObjectName("agentSchemeList")
        self.new_button = QPushButton("Создать AgentScheme", list_panel)
        self.new_button.setObjectName("newAgentSchemeButton")
        self.sort_button = QPushButton(
            "Сортировать по agent_scheme_id",
            list_panel,
        )
        self.sort_button.setObjectName("sortAgentSchemesButton")
        self.sort_button.setCheckable(True)
        self.delete_button = QPushButton("Удалить AgentScheme", list_panel)
        self.delete_button.setObjectName("deleteAgentSchemeButton")
        self.delete_button.setEnabled(False)
        self.export_button = QPushButton("Экспорт AgentScheme…", list_panel)
        self.export_button.setObjectName("exportAgentSchemeButton")
        self.export_button.setEnabled(False)
        list_layout.addWidget(self.agent_scheme_list)
        list_layout.addWidget(self.new_button)
        list_layout.addWidget(self.sort_button)
        list_layout.addWidget(self.export_button)
        list_layout.addWidget(self.delete_button)

        editor_panel = QWidget(splitter)
        editor_layout = QVBoxLayout(editor_panel)
        fields_layout = QFormLayout()

        self.agent_scheme_id_edit = QLineEdit()
        self.agent_scheme_id_edit.setObjectName("agentSchemeIdEdit")
        fields_layout.addRow("Идентификатор:", self.agent_scheme_id_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("agentSchemeNameEdit")
        fields_layout.addRow("Название:", self.name_edit)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setObjectName("agentSchemeDescriptionEdit")
        self.description_edit.setMaximumHeight(90)
        fields_layout.addRow("Описание:", self.description_edit)

        root_controls = QHBoxLayout()
        self.root_template_combo = QComboBox()
        self.root_template_combo.setObjectName("agentRootTemplateCombo")
        self.root_count_spin = QSpinBox()
        self.root_count_spin.setObjectName("agentRootCountSpin")
        self.root_count_spin.setRange(1, 100_000)
        self.root_count_spin.setValue(1)
        self.add_root_button = QPushButton("Добавить корень")
        self.add_root_button.setObjectName("addAgentRootButton")
        root_controls.addWidget(self.root_template_combo, 1)
        root_controls.addWidget(QLabel("Количество:"))
        root_controls.addWidget(self.root_count_spin)
        root_controls.addWidget(self.add_root_button)

        self.root_list = QListWidget()
        self.root_list.setObjectName("agentRootList")
        self.root_list.setMinimumHeight(110)
        self.remove_root_button = QPushButton("Удалить выбранный корень")
        self.remove_root_button.setObjectName("removeAgentRootButton")
        self.remove_root_button.setEnabled(False)

        self.tree_summary_label = QLabel("Узлов: 0 | join_id: 0")
        self.tree_summary_label.setObjectName("agentTreeSummaryLabel")
        self.tree = QTreeWidget()
        self.tree.setObjectName("agentTree")
        self.tree.setHeaderLabels(["Экземпляр", "full_path", "join_id"])
        self.tree.setUniformRowHeights(True)
        self.tree.setColumnWidth(0, 260)
        self.tree.setColumnWidth(1, 620)
        self.tree.setMinimumHeight(280)

        self.save_button = QPushButton("Сохранить AgentScheme")
        self.save_button.setObjectName("saveAgentSchemeButton")

        editor_layout.addLayout(fields_layout)
        editor_layout.addWidget(QLabel("Корневые шаблоны:"))
        editor_layout.addLayout(root_controls)
        editor_layout.addWidget(self.root_list)
        editor_layout.addWidget(self.remove_root_button)
        editor_layout.addWidget(QLabel("Вычисляемое дерево:"))
        editor_layout.addWidget(self.tree_summary_label)
        editor_layout.addWidget(self.tree, 1)
        editor_layout.addWidget(self.save_button)

        splitter.addWidget(list_panel)
        splitter.addWidget(editor_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self.unsaved = UnsavedChanges(
            self, [self.agent_scheme_id_edit, self.name_edit, self.description_edit],
            lambda: self.roots, self._save_agent_scheme, self._reset_draft,
        )
        self.new_button.clicked.connect(
            lambda: self.unsaved.run(self._new_agent_scheme)
        )
        self.sort_button.toggled.connect(self._sort_agent_schemes)
        self.delete_button.clicked.connect(
            lambda: self.unsaved.run(self._delete_selected_agent_scheme)
        )
        self.save_button.clicked.connect(self.unsaved.save_changes)
        self.export_button.clicked.connect(
            lambda: self.unsaved.run(self._export_agent_scheme)
        )
        self.agent_scheme_list.currentItemChanged.connect(
            self._selection_changed
        )
        self.add_root_button.clicked.connect(self._add_root)
        self.remove_root_button.clicked.connect(self._remove_root)
        self.root_list.currentItemChanged.connect(
            lambda current, previous: self.remove_root_button.setEnabled(
                current is not None
            )
        )

        self._reload_agent_schemes()
        if self.agent_scheme_list.count() == 0:
            self._new_agent_scheme()

    def refresh(self) -> None:
        self._reload_agent_schemes(self._selected_agent_scheme_id())

    def _reset_draft(self) -> None:
        agent_scheme_id = self._selected_agent_scheme_id()
        if agent_scheme_id is None:
            self._new_agent_scheme()
        else:
            self._load_selected_agent_scheme(agent_scheme_id)

    def _new_agent_scheme(self) -> None:
        with QSignalBlocker(self.agent_scheme_list):
            self.agent_scheme_list.setCurrentRow(-1)
        self.delete_button.setEnabled(False)
        self.export_button.setEnabled(False)
        self.agent_scheme_id_edit.setEnabled(True)
        self.agent_scheme_id_edit.clear()
        self.name_edit.clear()
        self.description_edit.clear()
        self.roots = []
        self._reload_root_list()
        self._reload_root_choices()
        self._reload_tree()
        self.agent_scheme_id_edit.setFocus()
        self.unsaved.mark_clean()

    def _save_agent_scheme(self) -> bool:
        try:
            agent_scheme = self._collect_agent_scheme()
            save_agent_scheme(self.project_path, agent_scheme)
        except InvalidAgentSchemeError as error:
            QMessageBox.warning(
                self,
                "Не удалось сохранить AgentScheme",
                str(error),
            )
            return False
        self.unsaved.mark_clean()
        self._reload_agent_schemes(
            selected_agent_scheme_id=str(agent_scheme["agent_scheme_id"])
        )
        return True

    def _export_agent_scheme(self) -> None:
        agent_scheme_id = self._selected_agent_scheme_id()
        if agent_scheme_id is None:
            return
        revision, accepted = QInputDialog.getInt(
            self, "Экспорт AgentScheme", "Ревизия схемы:", 1, 1, 2_147_483_647,
        )
        if not accepted:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Экспорт AgentScheme",
            str(self.project_path / f"{agent_scheme_id}.agent.json"),
            "JSON (*.json)",
        )
        if not filename:
            return
        destination = export_agent_scheme(
            self.project_path, self.agent_schemes[agent_scheme_id],
            Path(filename), revision,
        )
        QMessageBox.information(
            self, "AgentScheme экспортирована", f"Файл сохранён:\n{destination}",
        )

    def _collect_agent_scheme(self) -> dict[str, object]:
        name = self.name_edit.text().strip()
        return {
            "agent_scheme_id": self.agent_scheme_id_edit.text().strip(),
            "name": name,
            "description": self.description_edit.toPlainText().strip() or name,
            "roots": [dict(root) for root in self.roots],
        }

    def _reload_agent_schemes(
        self,
        selected_agent_scheme_id: str | None = None,
    ) -> None:
        self.templates = {
            str(template["template_id"]): template
            for template in load_templates(self.project_path)
        }
        self.agent_schemes = {
            str(agent_scheme["agent_scheme_id"]): agent_scheme
            for agent_scheme in load_agent_schemes(self.project_path)
        }

        signal_blocker = QSignalBlocker(self.agent_scheme_list)
        self.agent_scheme_list.clear()
        agent_scheme_ids = list(self.agent_schemes)
        if self.sort_button.isChecked():
            agent_scheme_ids.sort(key=str.casefold)

        selected_item = None
        for agent_scheme_id in agent_scheme_ids:
            agent_scheme = self.agent_schemes[agent_scheme_id]
            item = QListWidgetItem(
                f"{agent_scheme_id} ({agent_scheme['name']})"
            )
            item.setData(Qt.ItemDataRole.UserRole, agent_scheme_id)
            missing_roots = [
                str(root["template_id"])
                for root in agent_scheme["roots"]
                if root["template_id"] not in self.templates
            ]
            if missing_roots:
                item.setForeground(MISSING_REFERENCE_BRUSH)
                item.setToolTip(
                    "Не найдены шаблоны: " + ", ".join(missing_roots)
                )
            else:
                item.setToolTip(agent_scheme_id)
            self.agent_scheme_list.addItem(item)
            if agent_scheme_id == selected_agent_scheme_id:
                selected_item = item
        del signal_blocker

        self.delete_button.setEnabled(False)
        self.export_button.setEnabled(False)
        if selected_item is not None:
            self.agent_scheme_list.setCurrentItem(selected_item)
        else:
            self._reload_root_choices()

    def _selection_changed(
        self,
        current_item: QListWidgetItem | None,
        previous_item: QListWidgetItem | None,
    ) -> None:
        self.unsaved.select(
            self.agent_scheme_list, current_item, previous_item,
            self._load_selected_agent_scheme,
        )

    def _load_selected_agent_scheme(self, agent_scheme_id: str) -> None:
        agent_scheme = self.agent_schemes[agent_scheme_id]
        self.export_button.setEnabled(True)
        self.agent_scheme_id_edit.setText(agent_scheme_id)
        self.agent_scheme_id_edit.setEnabled(False)
        self.name_edit.setText(str(agent_scheme["name"]))
        self.description_edit.setPlainText(str(agent_scheme["description"]))
        self.roots = [dict(root) for root in agent_scheme["roots"]]
        self._reload_root_list()
        self._reload_root_choices()
        self._reload_tree()
        self.unsaved.mark_clean()

    def _reload_root_choices(self) -> None:
        self.root_template_combo.clear()
        root_template_ids = {
            str(root["template_id"])
            for root in self.roots
        }
        for template_id in sorted(self.templates, key=str.casefold):
            if template_id in root_template_ids:
                continue
            template = self.templates[template_id]
            self.root_template_combo.addItem(
                f"{template_id} ({template['name']})",
                template_id,
            )
        self.add_root_button.setEnabled(
            self.root_template_combo.count() > 0
        )

    def _reload_root_list(self) -> None:
        self.root_list.clear()
        for root in self.roots:
            template_id = str(root["template_id"])
            if template_id in self.templates:
                item = QListWidgetItem(f"{template_id} × {root['count']}")
            else:
                item = QListWidgetItem(
                    f"{template_id} × {root['count']} (шаблон не найден)"
                )
                item.setForeground(MISSING_REFERENCE_BRUSH)
                item.setToolTip("Шаблон не найден в текущем комплексе")
            item.setData(Qt.ItemDataRole.UserRole, template_id)
            self.root_list.addItem(item)
        self.remove_root_button.setEnabled(False)

    def _add_root(self) -> None:
        template_id = self.root_template_combo.currentData()
        if template_id is None:
            return
        self.roots.append({
            "count": self.root_count_spin.value(),
            "template_id": str(template_id),
        })
        self.root_count_spin.setValue(1)
        self._reload_root_list()
        self._reload_root_choices()
        self._reload_tree()

    def _remove_root(self) -> None:
        current_item = self.root_list.currentItem()
        if current_item is None:
            return
        template_id = str(current_item.data(Qt.ItemDataRole.UserRole))
        self.roots = [
            root
            for root in self.roots
            if root["template_id"] != template_id
        ]
        self._reload_root_list()
        self._reload_root_choices()
        self._reload_tree()

    def _reload_tree(self) -> None:
        self.tree.clear()
        if not self.roots:
            self.tree_summary_label.setText("Узлов: 0 | join_id: 0")
            return

        preview = {
            "agent_scheme_id": "preview",
            "name": "preview",
            "description": "preview",
            "roots": [dict(root) for root in self.roots],
        }
        try:
            roots = build_agent_tree(self.project_path, preview)
        except (InvalidAgentSchemeError, InvalidTemplateError) as error:
            self.tree_summary_label.setText(str(error))
            return

        node_count = 0
        self.tree.setUpdatesEnabled(False)

        def add_node(
            node: dict[str, object],
            parent_item: QTreeWidgetItem | None = None,
        ) -> None:
            nonlocal node_count
            node_count += 1
            join_id = str(node.get("join_id", ""))
            values = [
                f"{node['template_id']}[{node['index']}]",
                str(node["full_path"]),
                join_id,
            ]
            item = (
                QTreeWidgetItem(parent_item, values)
                if parent_item is not None
                else QTreeWidgetItem(self.tree, values)
            )
            if bool(node["missing"]):
                for column in range(3):
                    item.setForeground(column, MISSING_REFERENCE_BRUSH)
                item.setToolTip(0, "Шаблон не найден в текущем комплексе")
            for child in node["children"]:
                add_node(child, item)
            if parent_item is None:
                item.setExpanded(True)

        for root in roots:
            add_node(root)
        self.tree.setUpdatesEnabled(True)
        self.tree_summary_label.setText(
            f"Узлов: {node_count} | join_id: {len(roots)}"
        )

    def _sort_agent_schemes(self) -> None:
        if not self.unsaved.run(
            lambda: self._reload_agent_schemes(self._selected_agent_scheme_id())
        ):
            with QSignalBlocker(self.sort_button):
                self.sort_button.setChecked(not self.sort_button.isChecked())

    def _delete_selected_agent_scheme(self) -> None:
        agent_scheme_id = self._selected_agent_scheme_id()
        if agent_scheme_id is None:
            return
        name = str(self.agent_schemes[agent_scheme_id]["name"])
        answer = QMessageBox.question(
            self,
            "Удалить AgentScheme",
            f"Удалить AgentScheme «{name}» ({agent_scheme_id})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_agent_scheme(self.project_path, agent_scheme_id)
        except InvalidAgentSchemeError as error:
            QMessageBox.warning(
                self,
                "Не удалось удалить AgentScheme",
                str(error),
            )
            return

        self._reload_agent_schemes()
        if self.agent_scheme_list.count():
            self.agent_scheme_list.setCurrentRow(0)
        else:
            self._new_agent_scheme()

    def _selected_agent_scheme_id(self) -> str | None:
        current_item = self.agent_scheme_list.currentItem()
        if current_item is None:
            return None
        return str(current_item.data(Qt.ItemDataRole.UserRole))
