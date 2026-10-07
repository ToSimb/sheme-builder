from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.agent_scheme import build_agent_tree, load_agent_schemes
from scheme_builder.join_scheme import (
    build_join_tree,
    export_join_scheme,
    join_scheme_binding_issues,
    load_join_scheme,
    save_join_scheme,
)
from scheme_builder.template import load_templates
from scheme_builder.ui.reference_status import MISSING_REFERENCE_BRUSH
from scheme_builder.ui.unsaved_changes import EDITOR_ERRORS, UnsavedChanges


class JoinSchemeEditor(QWidget):
    def __init__(self, project_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.project_path = project_path
        self.root_template_combo = QComboBox()
        self.root_template_combo.setObjectName("joinRootTemplateCombo")
        fields = QFormLayout()
        fields.addRow("Корневой шаблон комплекса:", self.root_template_combo)

        self.summary_label = QLabel("Выберите корневой шаблон.")
        self.summary_label.setObjectName("joinTreeSummaryLabel")
        self.tree = QTreeWidget()
        self.tree.setObjectName("joinTree")
        self.tree.setHeaderLabels(["Экземпляр", "full_path"])
        self.tree.setUniformRowHeights(True)
        self.tree.setColumnWidth(0, 300)
        self.tree.setColumnWidth(1, 620)
        self.save_button = QPushButton("Сохранить JoinScheme")
        self.save_button.setObjectName("saveJoinSchemeButton")
        self.export_button = QPushButton("Экспорт JoinScheme…")
        self.export_button.setObjectName("exportJoinSchemeButton")

        self.agents = []
        self.definitions = []
        self._had_agents = False
        self.agents_table = QTableWidget(0, 2)
        self.agents_table.setObjectName("joinAgentsTable")
        self.agents_table.setHorizontalHeaderLabels(["agent_reg_id", "AgentScheme"])
        self.agents_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.agents_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.agents_table.horizontalHeader().setStretchLastSection(True)
        self.bindings_table = QTableWidget(0, 3)
        self.bindings_table.setObjectName("joinBindingsTable")
        self.bindings_table.setHorizontalHeaderLabels(["join_id", "Корень (сохранённый → текущий)", "Назначение full_path"])
        self.bindings_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bindings_table.setColumnWidth(1, 280)
        self.bindings_table.horizontalHeader().setStretchLastSection(True)
        self.issues_label = QLabel()
        self.issues_label.setObjectName("joinBindingIssuesLabel")
        self.issues_label.setWordWrap(True)
        self.issues_label.setStyleSheet("color: #c62828")
        self.issues_label.setTextFormat(Qt.TextFormat.PlainText)
        buttons = QHBoxLayout()
        self.add_agent_button = QPushButton("Добавить агента")
        self.remove_agent_button = QPushButton("Удалить агента")
        buttons.addWidget(self.add_agent_button)
        buttons.addWidget(self.remove_agent_button)

        layout = QVBoxLayout(self)
        layout.addLayout(fields)
        layout.addWidget(QLabel(
            "Привязки jtAssign: один AgentScheme можно использовать для нескольких агентов. "
            "Назначение — узел того же шаблона."
        ))
        layout.addWidget(self.summary_label)
        layout.addWidget(self.tree, 1)
        layout.addLayout(buttons)
        layout.addWidget(self.agents_table)
        layout.addWidget(self.bindings_table)
        layout.addWidget(self.issues_label)
        layout.addWidget(self.save_button)
        layout.addWidget(self.export_button)

        self.unsaved = UnsavedChanges(
            self, [], self._draft,
            self._save, self.refresh,
        )
        self.root_template_combo.currentIndexChanged.connect(self._root_changed)
        self.agents_table.currentCellChanged.connect(self._reload_bindings)
        self.add_agent_button.clicked.connect(self._add_agent)
        self.remove_agent_button.clicked.connect(self._remove_agent)
        self.save_button.clicked.connect(self.unsaved.save_changes)
        self.export_button.clicked.connect(
            lambda: self.unsaved.run(self._export)
        )
        self.refresh()

    def refresh(self) -> None:
        scheme = load_join_scheme(self.project_path)
        templates = load_templates(self.project_path)
        self.definitions = load_agent_schemes(self.project_path)
        self.agents = scheme.get("agents", []) if scheme else []
        self._had_agents = bool(scheme and "agents" in scheme)
        selected_id = scheme["root_template_id"] if scheme else None
        with QSignalBlocker(self.root_template_combo):
            self.root_template_combo.clear()
            self.root_template_combo.addItem("— Выберите шаблон —", None)
            for template in sorted(templates, key=lambda item: item["template_id"].casefold()):
                self.root_template_combo.addItem(
                    f"{template['template_id']} ({template['name']})",
                    template["template_id"],
                )
            index = self.root_template_combo.findData(selected_id)
            if selected_id is not None and index < 0:
                self.root_template_combo.addItem(
                    f"{selected_id} (шаблон не найден)", selected_id,
                )
                index = self.root_template_combo.count() - 1
                self.root_template_combo.setItemData(
                    index, MISSING_REFERENCE_BRUSH, Qt.ItemDataRole.ForegroundRole,
                )
            self.root_template_combo.setCurrentIndex(max(index, 0))
        self._reload_tree()
        self._render_agents(0)
        self.unsaved.mark_clean()

    def _draft(self):
        scheme = {"root_template_id": self.root_template_combo.currentData()}
        if self.agents or self._had_agents:
            scheme["agents"] = self.agents
        return scheme

    def _save(self) -> bool:
        save_join_scheme(self.project_path, self._draft())
        self.unsaved.mark_clean()
        return True

    def _export(self) -> None:
        if self.root_template_combo.currentData() is None:
            return
        revision, accepted = QInputDialog.getInt(
            self, "Экспорт JoinScheme", "Ревизия схемы:",
            1, 1, 2_147_483_647,
        )
        if not accepted:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "Экспорт JoinScheme",
            str(self.project_path / "join_scheme.export.json"),
            "JSON (*.json)",
        )
        if not filename:
            return
        destination = export_join_scheme(
            self.project_path, self._draft(), Path(filename), revision,
        )
        QMessageBox.information(
            self, "JoinScheme экспортирована", f"Файл сохранён:\n{destination}",
        )

    def _root_changed(self, *_args):
        self._reload_tree()
        self._reload_bindings()

    def _update_issues(self):
        try:
            issues = join_scheme_binding_issues(self.project_path, self._draft())
            self.issues_label.setText("\n".join(issues))
        except EDITOR_ERRORS as error:
            self.issues_label.setText(str(error))

    def _add_agent(self):
        self.agents.append({"agent_reg_id": "", "agent_scheme_id": "", "joins": []})
        self._render_agents(len(self.agents) - 1)
        self.agents_table.cellWidget(len(self.agents) - 1, 0).setFocus()

    def _remove_agent(self):
        row = self.agents_table.currentRow()
        if 0 <= row < len(self.agents):
            del self.agents[row]
            self._render_agents(min(row, len(self.agents) - 1))
            self._reload_tree()

    def _render_agents(self, selected):
        # Permanent cell widgets update the draft on every keystroke, not focus loss.
        with QSignalBlocker(self.agents_table):
            self.agents_table.setRowCount(0)
            self.agents_table.setRowCount(len(self.agents))
            for row, agent in enumerate(self.agents):
                field = QLineEdit(agent["agent_reg_id"])
                field.textChanged.connect(lambda text, a=agent: self._agent_text(a, text))
                self.agents_table.setCellWidget(row, 0, field)
                combo = QComboBox()
                combo.addItem("— Выберите AgentScheme —", "")
                for definition in self.definitions:
                    combo.addItem(f"{definition['agent_scheme_id']} ({definition['name']})", definition["agent_scheme_id"])
                index = combo.findData(agent["agent_scheme_id"])
                if index < 0:
                    combo.addItem(f"{agent['agent_scheme_id']} (не найдена)", agent["agent_scheme_id"])
                    index = combo.count() - 1
                    combo.setItemData(index, MISSING_REFERENCE_BRUSH, Qt.ItemDataRole.ForegroundRole)
                combo.setCurrentIndex(index)
                combo.currentIndexChanged.connect(lambda _index, a=agent, c=combo: self._agent_definition(a, c.currentData()))
                self.agents_table.setCellWidget(row, 1, combo)
            self.agents_table.setCurrentCell(selected, 0)
        self._reload_bindings()

    def _select_agent(self, agent):
        for row, candidate in enumerate(self.agents):
            if candidate is agent:
                if self.agents_table.currentRow() != row:
                    self.agents_table.setCurrentCell(row, 0)
                break

    def _agent_text(self, agent, text):
        agent["agent_reg_id"] = text
        self._select_agent(agent)
        self._reload_tree()
        self._reload_bindings()

    def _agent_definition(self, agent, scheme_id):
        agent["agent_scheme_id"] = scheme_id
        self._select_agent(agent)
        # Existing joins are kept even when the selected definition changes.
        self._reload_tree()
        self._reload_bindings()

    def _reload_bindings(self, *_args):
        self.bindings_table.setRowCount(0)
        row = self.agents_table.currentRow()
        self.remove_agent_button.setEnabled(0 <= row < len(self.agents))
        self._update_issues()
        if not 0 <= row < len(self.agents):
            return
        agent = self.agents[row]
        try:
            definition = next((d for d in self.definitions if d["agent_scheme_id"] == agent["agent_scheme_id"]), None)
            roots = {r["join_id"]: r for r in build_agent_tree(self.project_path, definition)} if definition else {}
            destinations = []
            if self.root_template_combo.currentData():
                pending = [build_join_tree(self.project_path, self._draft())]
                while pending:
                    node = pending.pop()
                    destinations.append(node)
                    pending.extend(reversed(node["children"]))
        except EDITOR_ERRORS as error:
            self.issues_label.setText(str(error))
            return
        joins = {j["agent_item_join_id"]: j for j in agent["joins"]}
        ids = list(roots) + [key for key in joins if key not in roots]
        self.bindings_table.setRowCount(len(ids))
        for row, join_id in enumerate(ids):
            root, join = roots.get(join_id), joins.get(join_id)
            old_path = join["agent_item_full_path"] if join else "—"
            current_path = root["full_path"] if root else "корень не найден"
            stale = not root or bool(join and old_path != current_path)
            self.bindings_table.setItem(row, 0, QTableWidgetItem(join_id))
            item = QTableWidgetItem(current_path if not join or old_path == current_path else f"{old_path} → {current_path}")
            if stale:
                item.setForeground(MISSING_REFERENCE_BRUSH)
            self.bindings_table.setItem(row, 1, item)
            combo = QComboBox()
            combo.addItem("— Без привязки / удалить —", None)
            if root and not root["missing"]:
                for node in destinations:
                    if not node["missing"] and node["template_id"] == root["template_id"]:
                        combo.addItem(node["full_path"], node["full_path"])
            path = join["join_item_full_path"] if join else None
            index = combo.findData(path)
            if index < 0:
                combo.addItem(f"{path} (недоступно)", path)
                index = combo.count() - 1
                combo.setItemData(index, MISSING_REFERENCE_BRUSH, Qt.ItemDataRole.ForegroundRole)
            combo.setCurrentIndex(index)
            if stale or (join and index > 0 and combo.itemText(index).endswith("(недоступно)")):
                combo.setStyleSheet("color: #c62828")
            # activated also fires when explicitly choosing the same target to confirm drift.
            combo.activated.connect(lambda _i, a=agent, key=join_id, r=root, c=combo: self._bind(a, key, r, c.currentData()))
            self.bindings_table.setCellWidget(row, 2, combo)

    def _bind(self, agent, join_id, root, path):
        if path is None:
            agent["joins"] = [j for j in agent["joins"] if j["agent_item_join_id"] != join_id]
        elif root:
            # An unavailable saved value is displayed for preservation, not a new choice.
            try:
                pending = [build_join_tree(self.project_path, self._draft())]
                valid = False
                while pending:
                    node = pending.pop()
                    if node["full_path"] == path and node["template_id"] == root["template_id"] and not node["missing"] and not root["missing"]:
                        valid = True
                    pending.extend(node["children"])
                if valid:
                    new_join = {"agent_item_join_id": join_id, "agent_item_full_path": root["full_path"], "join_item_full_path": path}
                    for index, old in enumerate(agent["joins"]):
                        if old["agent_item_join_id"] == join_id:
                            agent["joins"][index] = new_join
                            break
                    else:
                        agent["joins"].append(new_join)
            except EDITOR_ERRORS as error:
                self.issues_label.setText(str(error))
                return
        self._reload_bindings()

    def _reload_tree(self) -> None:
        self.tree.clear()
        template_id = self.root_template_combo.currentData()
        self.save_button.setEnabled(template_id is not None)
        self.export_button.setEnabled(template_id is not None)
        if template_id is None:
            self.summary_label.setText("Выберите корневой шаблон.")
            return
        try:
            root = build_join_tree(self.project_path, self._draft())
        except EDITOR_ERRORS as error:
            self.summary_label.setText(str(error))
            return

        count = 0
        missing = 0

        def add_node(node: dict[str, object], parent: QTreeWidgetItem | None) -> None:
            nonlocal count, missing
            count += 1
            label = str(node["full_path"]).rsplit("/", 1)[-1]
            item = QTreeWidgetItem([label, str(node["full_path"])])
            item.setData(0, Qt.ItemDataRole.UserRole, node["full_path"])
            if node["missing"]:
                missing += 1
                item.setForeground(0, MISSING_REFERENCE_BRUSH)
                item.setForeground(1, MISSING_REFERENCE_BRUSH)
                item.setToolTip(0, "Шаблон не найден в текущем комплексе")
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            for child in node["children"]:
                add_node(child, item)

        add_node(root, None)
        self.tree.expandToDepth(1)
        self.summary_label.setText(f"Узлов: {count} | Отсутствующих ссылок: {missing}")
