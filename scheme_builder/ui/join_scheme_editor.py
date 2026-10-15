from collections import Counter
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
    QLabel,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.agent_scheme import build_agent_tree, load_agent_schemes
from scheme_builder.join_scheme import (
    auto_assign_join_scheme,
    build_join_tree,
    export_join_scheme,
    join_scheme_binding_issues,
    load_join_scheme,
    save_join_scheme,
)
from scheme_builder.template import load_templates
from scheme_builder.ui.reference_status import MISSING_REFERENCE_BRUSH
from scheme_builder.ui.status_colors import (
    DANGER_BRUSH,
    DANGER_COLOR,
    DANGER_TEXT_COLOR,
    SUCCESS_BRUSH,
    SUCCESS_COLOR,
    SUCCESS_TEXT_COLOR,
    WARNING_BRUSH,
    WARNING_COLOR,
    WARNING_TEXT_COLOR,
    background_style,
)
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
        self.legend_label = QLabel(
            "○ свободно (жёлтый)   ✓ подключено (зелёный)   "
            "⚠ конфликт (красный)"
        )
        self.legend_label.setObjectName("joinTreeLegendLabel")
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
        self.issues_label.setStyleSheet(f"color: {DANGER_TEXT_COLOR}")
        self.issues_label.setTextFormat(Qt.TextFormat.PlainText)
        buttons = QGridLayout()
        self.add_agent_button = QPushButton("Добавить агента")
        self.remove_agent_button = QPushButton("Удалить агента")
        self.auto_assign_button = QPushButton("Автосборка")
        self.auto_assign_button.setObjectName("autoAssignJoinSchemeButton")
        self.remove_all_agents_button = QPushButton("Удалить всех агентов")
        self.remove_all_agents_button.setObjectName("removeAllJoinAgentsButton")
        buttons.addWidget(self.add_agent_button, 0, 0)
        buttons.addWidget(self.remove_agent_button, 0, 1)
        buttons.addWidget(self.auto_assign_button, 1, 0)
        buttons.addWidget(self.remove_all_agents_button, 1, 1)

        tree_panel = QWidget()
        tree_layout = QVBoxLayout(tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.addWidget(self.summary_label)
        tree_layout.addWidget(self.legend_label)
        tree_layout.addWidget(self.tree, 1)

        agents_panel = QWidget()
        agents_layout = QVBoxLayout(agents_panel)
        agents_layout.setContentsMargins(0, 0, 12, 0)
        agents_layout.addWidget(QLabel("Агенты и подключения"))
        agents_layout.addLayout(buttons)
        agents_layout.addWidget(self.agents_table)
        agents_layout.addWidget(self.bindings_table, 1)
        agents_layout.addWidget(self.issues_label)
        file_buttons = QHBoxLayout()
        file_buttons.addWidget(self.save_button)
        file_buttons.addWidget(self.export_button)
        agents_layout.addLayout(file_buttons)

        self.workspace_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.workspace_splitter.setObjectName("joinWorkspaceSplitter")
        self.workspace_splitter.addWidget(tree_panel)
        self.workspace_splitter.addWidget(agents_panel)
        self.workspace_splitter.setStretchFactor(0, 3)
        self.workspace_splitter.setStretchFactor(1, 2)
        self.workspace_splitter.setSizes([650, 550])

        layout = QVBoxLayout(self)
        layout.addLayout(fields)
        layout.addWidget(QLabel(
            "Привязки jtAssign: один AgentScheme можно использовать для нескольких агентов. "
            "Назначение — узел того же шаблона."
        ))
        layout.addWidget(self.workspace_splitter, 1)

        self.unsaved = UnsavedChanges(
            self, [], self._draft,
            self._save, self.refresh,
        )
        self.root_template_combo.currentIndexChanged.connect(self._root_changed)
        self.agents_table.currentCellChanged.connect(self._reload_bindings)
        self.add_agent_button.clicked.connect(self._add_agent)
        self.remove_agent_button.clicked.connect(self._remove_agent)
        self.auto_assign_button.clicked.connect(self._auto_assign)
        self.remove_all_agents_button.clicked.connect(self._remove_all_agents)
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
            warning_markers = (
                "введите agent_reg_id",
                "выберите AgentScheme",
                "отсутствует привязка",
                "Не хватает агентов AgentScheme",
                "Точка подключения не занята",
            )
            errors = [
                issue for issue in issues
                if not any(marker in issue for marker in warning_markers)
            ]
            if errors:
                self.issues_label.setStyleSheet(f"color: {DANGER_TEXT_COLOR}")
                self.issues_label.setText(
                    "Требуется исправить:\n" + "\n".join(issues)
                )
            elif issues:
                self.issues_label.setStyleSheet(f"color: {WARNING_TEXT_COLOR}")
                self.issues_label.setText(
                    "Требуется заполнить:\n" + "\n".join(issues)
                )
            elif self.root_template_combo.currentData() is not None:
                self.issues_label.setStyleSheet(f"color: {SUCCESS_TEXT_COLOR}")
                self.issues_label.setText("✓ JoinScheme готова к экспорту.")
            else:
                self.issues_label.clear()
        except EDITOR_ERRORS as error:
            self.issues_label.setStyleSheet(f"color: {DANGER_TEXT_COLOR}")
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

    def _remove_all_agents(self):
        if not self.agents:
            return
        answer = QMessageBox.question(
            self,
            "Удалить всех агентов",
            "Удалить всех агентов и их подключения из JoinScheme?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.agents = []
        self._had_agents = True
        self._render_agents(-1)
        self._reload_tree()

    def _auto_assign(self):
        try:
            scheme, messages = auto_assign_join_scheme(
                self.project_path, self._draft(),
            )
        except EDITOR_ERRORS as error:
            QMessageBox.warning(self, "Автосборка не выполнена", str(error))
            return
        self.agents = scheme.get("agents", [])
        self._had_agents = True
        self._render_agents(0 if self.agents else -1)
        self._reload_tree()
        if messages:
            QMessageBox.warning(
                self,
                "Автосборка требует уточнения",
                "\n".join(messages),
            )

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
            self._refresh_agent_statuses()
            self.agents_table.setCurrentCell(selected, 0)
        self._reload_bindings()

    def _refresh_agent_statuses(self):
        reg_ids = [str(agent["agent_reg_id"]).strip() for agent in self.agents]
        duplicate_ids = {
            reg_id for reg_id, count in Counter(reg_ids).items()
            if reg_id and count > 1
        }
        definition_ids = {
            str(definition["agent_scheme_id"])
            for definition in self.definitions
        }
        for row, agent in enumerate(self.agents):
            field = self.agents_table.cellWidget(row, 0)
            reg_id = reg_ids[row]
            if not reg_id:
                field.setStyleSheet(background_style(WARNING_COLOR))
                field.setToolTip("Введите уникальный agent_reg_id")
            elif reg_id in duplicate_ids:
                field.setStyleSheet(background_style(DANGER_COLOR))
                field.setToolTip("agent_reg_id повторяется")
            else:
                field.setStyleSheet(background_style(None))
                field.setToolTip("Уникальный agent_reg_id")

            combo = self.agents_table.cellWidget(row, 1)
            scheme_id = str(agent["agent_scheme_id"])
            if not scheme_id:
                combo.setStyleSheet(background_style(WARNING_COLOR))
                combo.setToolTip("Выберите AgentScheme")
            elif scheme_id not in definition_ids:
                combo.setStyleSheet(background_style(DANGER_COLOR))
                combo.setToolTip("AgentScheme не найдена")
            else:
                combo.setStyleSheet(background_style(None))
                combo.setToolTip("AgentScheme выбрана")

    def _select_agent(self, agent):
        for row, candidate in enumerate(self.agents):
            if candidate is agent:
                if self.agents_table.currentRow() != row:
                    self.agents_table.setCurrentCell(row, 0)
                break

    def _agent_text(self, agent, text):
        agent["agent_reg_id"] = text
        self._select_agent(agent)
        self._refresh_agent_statuses()
        self._reload_tree()
        self._reload_bindings()

    def _agent_definition(self, agent, scheme_id):
        agent["agent_scheme_id"] = scheme_id
        self._select_agent(agent)
        # Existing joins are kept even when the selected definition changes.
        self._refresh_agent_statuses()
        self._reload_tree()
        self._reload_bindings()

    def _occupancy(
        self,
        excluded_agent=None,
        excluded_join_id=None,
        destinations=None,
    ):
        if destinations is None:
            destinations = []
            if self.root_template_combo.currentData():
                try:
                    destinations = [build_join_tree(self.project_path, self._draft())]
                    for node in destinations:
                        destinations.extend(node["children"])
                except EDITOR_ERRORS:
                    pass
        destination_by_path = {
            str(node["full_path"]): node
            for node in destinations
        }
        has_marked_targets = any(
            node["join_target"] for node in destinations
        )
        definitions = {
            definition["agent_scheme_id"]: definition
            for definition in self.definitions
        }
        occupied = {}
        for agent_index, agent in enumerate(self.agents, start=1):
            label = agent["agent_reg_id"].strip() or f"Агент #{agent_index}"
            definition = definitions.get(agent["agent_scheme_id"])
            roots = {}
            if definition is not None:
                try:
                    roots = {
                        root["join_id"]: root
                        for root in build_agent_tree(self.project_path, definition)
                    }
                except EDITOR_ERRORS:
                    pass
            for join in agent["joins"]:
                if (
                    agent is excluded_agent
                    and join["agent_item_join_id"] == excluded_join_id
                ):
                    continue
                path = str(join["join_item_full_path"])
                root = roots.get(join["agent_item_join_id"])
                destination = destination_by_path.get(path)
                valid = bool(
                    root is not None
                    and not root["missing"]
                    and root["full_path"] == join["agent_item_full_path"]
                    and destination is not None
                    and not destination["missing"]
                    and root["template_id"] == destination["template_id"]
                    and (
                        not has_marked_targets
                        or destination["join_target"]
                    )
                )
                occupied.setdefault(path, []).append(
                    (f"{label}, join_id={join['agent_item_join_id']}", valid)
                )
        return occupied

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
            has_marked_targets = any(node["join_target"] for node in destinations)
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
            join_id_item = QTableWidgetItem(join_id)
            self.bindings_table.setItem(row, 0, join_id_item)
            root_item = QTableWidgetItem(
                current_path
                if not join or old_path == current_path
                else f"{old_path} → {current_path}"
            )
            if stale:
                root_item.setForeground(MISSING_REFERENCE_BRUSH)
            self.bindings_table.setItem(row, 1, root_item)
            combo = QComboBox()
            combo.addItem("— Без привязки / удалить —", None)
            occupied = self._occupancy(agent, join_id, destinations)
            if root and not root["missing"]:
                for node in destinations:
                    if (
                        not node["missing"]
                        and node["template_id"] == root["template_id"]
                        and (not has_marked_targets or node["join_target"])
                    ):
                        destination_path = str(node["full_path"])
                        users = [
                            label
                            for label, _valid in occupied.get(destination_path, [])
                        ]
                        text = destination_path
                        if users:
                            text += f" (занято: {', '.join(users)})"
                        combo.addItem(text, destination_path)
                        if users:
                            combo.model().item(combo.count() - 1).setEnabled(False)
            path = join["join_item_full_path"] if join else None
            index = combo.findData(path)
            unavailable = index < 0
            if unavailable:
                combo.addItem(f"{path} (недоступно)", path)
                index = combo.count() - 1
                combo.setItemData(index, MISSING_REFERENCE_BRUSH, Qt.ItemDataRole.ForegroundRole)
            combo.setCurrentIndex(index)
            conflicted = bool(path and occupied.get(path))
            if stale or unavailable or conflicted:
                status_brush = DANGER_BRUSH
                status_color = DANGER_COLOR
                status_text = "Подключение требует исправления"
            elif join:
                status_brush = SUCCESS_BRUSH
                status_color = SUCCESS_COLOR
                status_text = "Подключение корректно"
            else:
                status_brush = WARNING_BRUSH
                status_color = WARNING_COLOR
                status_text = "Подключение не назначено"
            join_id_item.setBackground(status_brush)
            join_id_item.setToolTip(status_text)
            root_item.setBackground(status_brush)
            root_item.setToolTip(status_text)
            combo.setStyleSheet(background_style(status_color))
            combo.setToolTip(status_text)
            # activated also fires when explicitly choosing the same target to confirm drift.
            combo.activated.connect(lambda _i, a=agent, key=join_id, r=root, c=combo: self._bind(a, key, r, c.currentData()))
            self.bindings_table.setCellWidget(row, 2, combo)

    def _bind(self, agent, join_id, root, path):
        if path is None:
            agent["joins"] = [
                join for join in agent["joins"]
                if join["agent_item_join_id"] != join_id
            ]
        elif root:
            # An unavailable saved value is displayed for preservation, not a new choice.
            try:
                nodes = [build_join_tree(self.project_path, self._draft())]
                for node in nodes:
                    nodes.extend(node["children"])
                has_marked_targets = any(node["join_target"] for node in nodes)
                valid = any(
                    node["full_path"] == path
                    and node["template_id"] == root["template_id"]
                    and not node["missing"]
                    and not root["missing"]
                    and (not has_marked_targets or node["join_target"])
                    for node in nodes
                )
                valid = valid and not self._occupancy(agent, join_id).get(path)
                if valid:
                    new_join = {
                        "agent_item_join_id": join_id,
                        "agent_item_full_path": root["full_path"],
                        "join_item_full_path": path,
                    }
                    for index, old in enumerate(agent["joins"]):
                        if old["agent_item_join_id"] == join_id:
                            agent["joins"][index] = new_join
                            break
                    else:
                        agent["joins"].append(new_join)
            except EDITOR_ERRORS as error:
                self.issues_label.setText(str(error))
                return
        self._reload_tree()
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
        targets = 0
        occupied_targets = 0
        conflicts = 0
        destinations = [root]
        for node in destinations:
            destinations.extend(node["children"])
        occupied = self._occupancy(destinations=destinations)
        has_marked_targets = any(
            node["join_target"] for node in destinations
        )
        selected_definition_ids = {
            agent["agent_scheme_id"] for agent in self.agents
        }
        legacy_target_template_ids = {
            root_definition["template_id"]
            for definition in self.definitions
            if definition["agent_scheme_id"] in selected_definition_ids
            for root_definition in definition["roots"]
        }

        def add_node(node: dict[str, object], parent: QTreeWidgetItem | None) -> None:
            nonlocal count, missing, targets, occupied_targets, conflicts
            count += 1
            path = str(node["full_path"])
            label = path.rsplit("/", 1)[-1]
            claims = occupied.get(path, [])
            users = [claim_label for claim_label, _valid in claims]
            legacy_target = (
                not has_marked_targets
                and node["template_id"] in legacy_target_template_ids
            )
            is_target = bool(node["join_target"] or legacy_target)
            valid_connection = bool(
                len(claims) == 1
                and claims[0][1]
                and not node["missing"]
            )
            connection_error = bool(
                node["missing"]
                or (claims and not valid_connection)
            )
            if is_target:
                targets += 1
            if valid_connection:
                if is_target:
                    occupied_targets += 1
                label = f"✓ {label}"
            elif claims or (is_target and node["missing"]):
                conflicts += 1
                label = f"⚠ {label}"
            elif is_target:
                label = f"○ {label}"
            item = QTreeWidgetItem([label, path])
            item.setData(0, Qt.ItemDataRole.UserRole, node["full_path"])
            if is_target or claims:
                if connection_error:
                    status_brush = DANGER_BRUSH
                    status_text = (
                        "Некорректное подключение: " + "; ".join(users)
                        if users
                        else "Точка подключения недоступна"
                    )
                elif valid_connection:
                    status_brush = SUCCESS_BRUSH
                    status_text = "Подключено: " + users[0]
                else:
                    status_brush = WARNING_BRUSH
                    status_text = "Свободная точка подключения: назначьте агента"
                item.setBackground(0, status_brush)
                item.setBackground(1, status_brush)
                item.setToolTip(0, status_text)
                item.setToolTip(1, status_text)
            if node["missing"]:
                missing += 1
                item.setForeground(0, MISSING_REFERENCE_BRUSH)
                item.setForeground(1, MISSING_REFERENCE_BRUSH)
                item.setToolTip(0, "Шаблон не найден в текущем комплексе")
            elif connection_error:
                item.setForeground(0, MISSING_REFERENCE_BRUSH)
                item.setForeground(1, MISSING_REFERENCE_BRUSH)
            if parent is None:
                self.tree.addTopLevelItem(item)
            else:
                parent.addChild(item)
            for child in node["children"]:
                add_node(child, item)

        add_node(root, None)
        self.tree.expandToDepth(1)
        self.summary_label.setText(
            f"Узлов: {count} | Точек: {targets} | Занято: {occupied_targets} | "
            f"Конфликтов: {conflicts} | Отсутствующих ссылок: {missing}"
        )
