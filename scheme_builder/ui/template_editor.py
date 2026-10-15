from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.config import (
    CATALOG_LIST_WIDTH,
    TEMPLATE_METRIC_LIST_MIN_HEIGHT,
)
from scheme_builder.metric import InvalidMetricError, load_metrics
from scheme_builder.join_scheme import load_join_scheme
from scheme_builder.template import (
    InvalidTemplateError,
    delete_template,
    load_templates,
    save_template,
)
from scheme_builder.ui.metric_list import apply_metric_group_stripes
from scheme_builder.ui.reference_status import MISSING_REFERENCE_BRUSH
from scheme_builder.ui.status_colors import (
    DANGER_BRUSH,
    SUCCESS_BRUSH,
    WARNING_BRUSH,
)
from scheme_builder.ui.unsaved_changes import UnsavedChanges
from scheme_builder.ui.usage_status import apply_usage_marks
from scheme_builder.agent_scheme import load_agent_schemes


TEMPLATE_HIERARCHY_LIMIT = 10_000


class TemplateEditor(QWidget):
    def __init__(self, project_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.project_path = project_path
        self.metrics: dict[str, dict[str, object]] = {}
        self.templates: dict[str, dict[str, object]] = {}
        self.includes: list[dict[str, int | str]] = []
        self.root_template_id: str | None = None
        self._hierarchy_items_by_template_id: dict[
            str, list[QTreeWidgetItem]
        ] = {}

        self.editor_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.editor_splitter.setObjectName("templateEditorSplitter")

        list_panel = QWidget(self.editor_splitter)
        list_panel.setMinimumWidth(CATALOG_LIST_WIDTH)
        list_layout = QVBoxLayout(list_panel)
        self.template_list = QListWidget(list_panel)
        self.template_list.setObjectName("templateList")
        self.new_button = QPushButton("Создать шаблон", list_panel)
        self.new_button.setObjectName("newTemplateButton")
        self.duplicate_button = QPushButton("Дублировать", list_panel)
        self.duplicate_button.setObjectName("duplicateTemplateButton")
        self.duplicate_button.setEnabled(False)
        self.sort_button = QPushButton("Сортировать по template_id", list_panel)
        self.sort_button.setObjectName("sortTemplatesButton")
        self.sort_button.setCheckable(True)
        self.delete_button = QPushButton("Удалить шаблон", list_panel)
        self.delete_button.setObjectName("deleteTemplateButton")
        self.delete_button.setEnabled(False)
        list_layout.addWidget(self.template_list)
        list_layout.addWidget(self.new_button)
        list_layout.addWidget(self.duplicate_button)
        list_layout.addWidget(self.sort_button)
        list_layout.addWidget(self.delete_button)

        scroll_area = QScrollArea(self.editor_splitter)
        scroll_area.setWidgetResizable(True)
        form_panel = QWidget()
        form_layout = QVBoxLayout(form_panel)
        fields_layout = QFormLayout()

        self.template_id_edit = QLineEdit()
        self.template_id_edit.setObjectName("templateIdEdit")
        fields_layout.addRow("Идентификатор:", self.template_id_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("templateNameEdit")
        fields_layout.addRow("Название:", self.name_edit)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setObjectName("templateDescriptionEdit")
        self.description_edit.setMaximumHeight(90)
        fields_layout.addRow("Описание:", self.description_edit)

        self.metric_list = QListWidget()
        self.metric_list.setObjectName("templateMetricList")
        self.metric_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.metric_list.setMinimumHeight(TEMPLATE_METRIC_LIST_MIN_HEIGHT)

        include_controls = QHBoxLayout()
        self.include_template_combo = QComboBox()
        self.include_template_combo.setObjectName("includeTemplateCombo")
        self.include_count_spin = QSpinBox()
        self.include_count_spin.setObjectName("includeCountSpin")
        self.include_count_spin.setRange(1, 1_000_000)
        self.include_count_spin.setValue(1)
        self.add_include_button = QPushButton("Добавить")
        self.add_include_button.setObjectName("addIncludeButton")
        include_controls.addWidget(self.include_template_combo, 1)
        include_controls.addWidget(QLabel("Количество:"))
        include_controls.addWidget(self.include_count_spin)
        include_controls.addWidget(self.add_include_button)

        self.include_list = QListWidget()
        self.include_list.setObjectName("templateIncludeList")
        self.include_list.setMinimumHeight(100)
        self.remove_include_button = QPushButton("Удалить выбранное включение")
        self.remove_include_button.setObjectName("removeIncludeButton")
        self.remove_include_button.setEnabled(False)

        self.save_button = QPushButton("Сохранить", form_panel)
        self.save_button.setObjectName("saveTemplateButton")

        form_layout.addLayout(fields_layout)
        form_layout.addWidget(QLabel("Метрики шаблона:"))
        form_layout.addWidget(self.metric_list)
        form_layout.addWidget(QLabel(
            "Дочерние шаблоны (галочка — точка подключения агента):"
        ))
        form_layout.addLayout(include_controls)
        form_layout.addWidget(self.include_list)
        form_layout.addWidget(self.remove_include_button)
        form_layout.addWidget(self.save_button)
        form_layout.addStretch()
        scroll_area.setWidget(form_panel)

        hierarchy_panel = QWidget(self.editor_splitter)
        hierarchy_panel.setMinimumWidth(CATALOG_LIST_WIDTH)
        hierarchy_layout = QVBoxLayout(hierarchy_panel)
        hierarchy_layout.addWidget(QLabel("<b>Иерархия шаблонов</b>"))
        self.hierarchy_summary_label = QLabel()
        self.hierarchy_summary_label.setObjectName("templateHierarchySummaryLabel")
        self.hierarchy_tree = QTreeWidget()
        self.hierarchy_tree.setObjectName("templateHierarchyTree")
        self.hierarchy_tree.setHeaderLabels(["Шаблон", "Количество"])
        self.hierarchy_tree.setAlternatingRowColors(True)
        self.hierarchy_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )
        hierarchy_header = self.hierarchy_tree.header()
        hierarchy_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        hierarchy_header.setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        hierarchy_layout.addWidget(self.hierarchy_summary_label)
        hierarchy_layout.addWidget(self.hierarchy_tree, 1)

        self.editor_splitter.addWidget(list_panel)
        self.editor_splitter.addWidget(scroll_area)
        self.editor_splitter.addWidget(hierarchy_panel)
        self.editor_splitter.setStretchFactor(0, 1)
        self.editor_splitter.setStretchFactor(1, 3)
        self.editor_splitter.setStretchFactor(2, 2)
        self.editor_splitter.setSizes([240, 520, 380])

        layout = QVBoxLayout(self)
        layout.addWidget(self.editor_splitter)

        self.unsaved = UnsavedChanges(
            self, [self.template_id_edit, self.name_edit, self.description_edit],
            lambda: (self.includes, [
                self.metric_list.item(row).data(Qt.ItemDataRole.UserRole)
                for row in range(self.metric_list.count())
                if self.metric_list.item(row).checkState() == Qt.CheckState.Checked
            ]),
            self._save_template, self._reset_draft,
        )
        self.new_button.clicked.connect(lambda: self.unsaved.run(self._new_template))
        self.duplicate_button.clicked.connect(
            lambda: self.unsaved.run(self._duplicate_template)
        )
        self.sort_button.toggled.connect(self._sort_templates)
        self.delete_button.clicked.connect(
            lambda: self.unsaved.run(self._delete_selected_template)
        )
        self.save_button.clicked.connect(self.unsaved.save_changes)
        self.template_list.currentItemChanged.connect(self._selection_changed)
        self.template_list.currentItemChanged.connect(
            lambda: self.duplicate_button.setEnabled(
                self._selected_template_id() is not None
            )
        )
        self.add_include_button.clicked.connect(self._add_include)
        self.remove_include_button.clicked.connect(self._remove_include)
        self.include_list.currentItemChanged.connect(
            lambda current, previous: self.remove_include_button.setEnabled(
                current is not None
            )
        )
        self.include_list.itemChanged.connect(self._include_target_changed)
        self.template_id_edit.textChanged.connect(
            lambda _text: self._reload_hierarchy()
        )
        self.name_edit.textChanged.connect(lambda _text: self._reload_hierarchy())

        self._reload_templates()
        if self.template_list.count() == 0:
            self._new_template()

    def refresh(self) -> None:
        self._reload_templates(self._selected_template_id())

    def _duplicate_template(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            return
        templates = {
            template["template_id"]: template
            for template in load_templates(self.project_path)
        }
        if template_id not in templates:
            raise InvalidTemplateError(f"Шаблон '{template_id}' не найден.")
        duplicate = dict(templates[template_id])
        copy_id = template_id + "_copy"
        while copy_id in templates:
            copy_id += "_copy"
        duplicate["template_id"] = copy_id
        duplicate["name"] += "_copy"
        save_template(self.project_path, duplicate)
        self._reload_templates(copy_id)

    def _reset_draft(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            self._new_template()
        else:
            self._load_selected_template(template_id)

    def _new_template(self) -> None:
        with QSignalBlocker(self.template_list):
            self.template_list.setCurrentRow(-1)
        self.duplicate_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        self.template_id_edit.setEnabled(True)
        self.template_id_edit.clear()
        self.name_edit.clear()
        self.description_edit.clear()
        self.includes = []
        self._reload_metric_choices(set())
        self._reload_include_list()
        self._reload_include_choices(None)
        self._reload_hierarchy()
        self.template_id_edit.setFocus()
        self.unsaved.mark_clean()

    def _save_template(self) -> bool:
        try:
            template = self._collect_template()
            save_template(self.project_path, template)
        except (InvalidMetricError, InvalidTemplateError) as error:
            QMessageBox.warning(self, "Не удалось сохранить шаблон", str(error))
            return False

        self.unsaved.mark_clean()
        self._reload_templates(selected_template_id=str(template["template_id"]))
        return True

    def _collect_template(self) -> dict[str, object]:
        name = self.name_edit.text().strip()
        template: dict[str, object] = {
            "template_id": self.template_id_edit.text().strip(),
            "name": name,
            "description": self.description_edit.toPlainText().strip() or name,
        }

        selected_metrics = [
            str(self.metric_list.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.metric_list.count())
            if self.metric_list.item(row).checkState() == Qt.CheckState.Checked
        ]
        if selected_metrics:
            template["metrics"] = selected_metrics
        if self.includes:
            template["includes"] = [dict(include) for include in self.includes]
        return template

    def _reload_templates(self, selected_template_id: str | None = None) -> None:
        self.metrics = {
            str(metric["metric_id"]): metric
            for metric in load_metrics(self.project_path)
        }
        self.templates = {
            str(template["template_id"]): template
            for template in load_templates(self.project_path)
        }
        used_ids = {
            include["template_id"]
            for template in self.templates.values()
            for include in template.get("includes", [])
        }
        used_ids.update(
            root["template_id"]
            for agent in load_agent_schemes(self.project_path)
            for root in agent["roots"]
        )
        join_scheme = load_join_scheme(self.project_path)
        root_template_id = None
        if join_scheme is not None:
            root_template_id = str(join_scheme["root_template_id"])
            used_ids.add(root_template_id)
        self.root_template_id = root_template_id
        join_target_ids = {
            str(include["template_id"])
            for template in self.templates.values()
            for include in template.get("includes", [])
            if include.get("join_target", False)
        }
        signal_blocker = QSignalBlocker(self.template_list)
        self.template_list.clear()
        template_ids = list(self.templates)
        if self.sort_button.isChecked():
            template_ids.sort(key=str.casefold)

        selected_item = None
        for template_id in template_ids:
            template = self.templates[template_id]
            target_marker = "○ " if template_id in join_target_ids else ""
            item = QListWidgetItem(
                f"{target_marker}{template_id} ({template['name']})"
            )
            item.setData(Qt.ItemDataRole.UserRole, template_id)
            missing_metrics, missing_templates = self._missing_references(template)
            tooltip_parts = []
            if missing_metrics or missing_templates:
                item.setForeground(MISSING_REFERENCE_BRUSH)
                item.setBackground(DANGER_BRUSH)
                missing_parts = []
                if missing_metrics:
                    missing_parts.append("метрики: " + ", ".join(missing_metrics))
                if missing_templates:
                    missing_parts.append(
                        "шаблоны: " + ", ".join(missing_templates)
                    )
                tooltip_parts.append("Не найдены " + "; ".join(missing_parts))
            elif template_id == root_template_id:
                item.setBackground(SUCCESS_BRUSH)
            elif template_id in join_target_ids:
                item.setBackground(WARNING_BRUSH)
            if template_id == root_template_id:
                tooltip_parts.append("Корневой шаблон JoinScheme")
            if template_id in join_target_ids:
                tooltip_parts.append("Используется как точка подключения")
            item.setToolTip("\n".join(tooltip_parts) or template_id)
            self.template_list.addItem(item)
            if template_id == selected_template_id:
                selected_item = item
        apply_usage_marks(self.template_list, used_ids)
        del signal_blocker

        self.delete_button.setEnabled(False)
        if selected_item is not None:
            self.template_list.setCurrentItem(selected_item)
        else:
            self._reload_include_choices(None)
            self._reload_hierarchy()

    def _selection_changed(
        self,
        current_item: QListWidgetItem | None,
        previous_item: QListWidgetItem | None,
    ) -> None:
        self.unsaved.select(
            self.template_list, current_item, previous_item, self._load_selected_template
        )

    def _load_selected_template(self, template_id: str) -> None:
        template = self.templates[template_id]
        self.template_id_edit.setText(template_id)
        self.template_id_edit.setEnabled(False)
        self.name_edit.setText(str(template["name"]))
        self.description_edit.setPlainText(str(template["description"]))
        self.includes = [dict(include) for include in template.get("includes", [])]
        self._reload_metric_choices(set(template.get("metrics", [])))
        self._reload_include_list()
        self._reload_include_choices(template_id)
        self._reload_hierarchy()
        self.unsaved.mark_clean()

    def _reload_hierarchy(self) -> None:
        self.hierarchy_tree.clear()
        self._hierarchy_items_by_template_id = {}

        templates = {
            template_id: dict(template)
            for template_id, template in self.templates.items()
        }
        selected_template_id = self._selected_template_id()
        draft_template_id = self.template_id_edit.text().strip()
        if selected_template_id in templates:
            draft = dict(templates[selected_template_id])
            draft["name"] = self.name_edit.text().strip()
            if self.includes:
                draft["includes"] = [dict(include) for include in self.includes]
            else:
                draft.pop("includes", None)
            templates[selected_template_id] = draft
        elif draft_template_id and draft_template_id not in templates:
            templates[draft_template_id] = {
                "template_id": draft_template_id,
                "name": self.name_edit.text().strip(),
                "includes": [dict(include) for include in self.includes],
            }

        included_ids = {
            str(include["template_id"])
            for template in templates.values()
            for include in template.get("includes", [])
            if include["template_id"] in templates
        }
        top_level_ids: list[str] = []
        if self.root_template_id:
            top_level_ids.append(self.root_template_id)
        top_level_ids.extend(
            template_id
            for template_id in sorted(templates, key=str.casefold)
            if template_id not in included_ids
            and template_id != self.root_template_id
        )

        node_count = 0
        max_depth = 0
        truncated = False
        covered_ids: set[str] = set()

        def attach_item(
            item: QTreeWidgetItem,
            parent: QTreeWidgetItem | None,
        ) -> None:
            if parent is None:
                self.hierarchy_tree.addTopLevelItem(item)
            else:
                parent.addChild(item)

        def add_template(
            template_id: str,
            parent: QTreeWidgetItem | None,
            ancestors: frozenset[str],
            depth: int,
            include: dict[str, object] | None = None,
        ) -> None:
            nonlocal node_count, max_depth, truncated
            if node_count >= TEMPLATE_HIERARCHY_LIMIT:
                if not truncated:
                    warning_item = QTreeWidgetItem([
                        "⚠ Иерархия сокращена",
                        "",
                    ])
                    warning_item.setBackground(0, DANGER_BRUSH)
                    warning_item.setToolTip(
                        0,
                        f"Показаны первые {TEMPLATE_HIERARCHY_LIMIT} узлов",
                    )
                    attach_item(warning_item, parent)
                    truncated = True
                return

            template = templates.get(template_id)
            is_cycle = template_id in ancestors
            is_missing = template is None
            is_join_target = bool(
                include is not None and include.get("join_target", False)
            )

            if is_cycle:
                label = f"⚠ {template_id} (цикл)"
            elif is_missing:
                label = f"⚠ {template_id} (шаблон не найден)"
            else:
                if template_id == self.root_template_id:
                    marker = "✓ "
                elif is_join_target:
                    marker = "○ "
                else:
                    marker = ""
                name = str(template["name"])
                label = f"{marker}{template_id}"
                if name:
                    label += f" ({name})"

            count_text = "—" if include is None else f"× {include['count']}"
            item = QTreeWidgetItem([label, count_text])
            item.setData(0, Qt.ItemDataRole.UserRole, template_id)
            attach_item(item, parent)
            node_count += 1
            max_depth = max(max_depth, depth)

            if is_cycle:
                item.setBackground(0, DANGER_BRUSH)
                item.setBackground(1, DANGER_BRUSH)
                item.setForeground(0, MISSING_REFERENCE_BRUSH)
                item.setToolTip(0, "Включения шаблонов образуют цикл")
                return
            if is_missing:
                item.setBackground(0, DANGER_BRUSH)
                item.setBackground(1, DANGER_BRUSH)
                item.setForeground(0, MISSING_REFERENCE_BRUSH)
                item.setToolTip(0, "Шаблон не найден в текущем комплексе")
                return
            covered_ids.add(template_id)
            self._hierarchy_items_by_template_id.setdefault(
                template_id, []
            ).append(item)
            if template_id == self.root_template_id:
                item.setBackground(0, SUCCESS_BRUSH)
                item.setBackground(1, SUCCESS_BRUSH)
                item.setToolTip(0, "Корневой шаблон комплекса")
            elif is_join_target:
                item.setBackground(0, WARNING_BRUSH)
                item.setBackground(1, WARNING_BRUSH)
                item.setToolTip(0, "Точка подключения агента")

            child_ancestors = ancestors | {template_id}
            for child_include in template.get("includes", []):
                add_template(
                    str(child_include["template_id"]),
                    item,
                    child_ancestors,
                    depth + 1,
                    child_include,
                )

        displayed_top_level_ids: list[str] = []
        for template_id in top_level_ids:
            previous_node_count = node_count
            add_template(template_id, None, frozenset(), 0)
            if node_count > previous_node_count:
                displayed_top_level_ids.append(template_id)
            if truncated:
                break
        top_level_ids = displayed_top_level_ids

        for template_id in sorted(templates, key=str.casefold):
            if template_id not in covered_ids:
                previous_node_count = node_count
                add_template(template_id, None, frozenset(), 0)
                if node_count > previous_node_count:
                    top_level_ids.append(template_id)
                if truncated:
                    break

        if not top_level_ids:
            placeholder = QTreeWidgetItem(["Шаблоны ещё не созданы", ""])
            self.hierarchy_tree.addTopLevelItem(placeholder)

        level_count = max_depth + 1 if node_count else 0
        summary = (
            f"Шаблонов: {len(templates)} | Верхний уровень: "
            f"{len(top_level_ids)} | Узлов: {node_count} | Уровней: {level_count}"
        )
        if truncated:
            summary += f" | Лимит: {TEMPLATE_HIERARCHY_LIMIT}"
        self.hierarchy_summary_label.setText(summary)
        self.hierarchy_tree.expandToDepth(3)
        selected_items = self._hierarchy_items_by_template_id.get(
            selected_template_id or "", []
        )
        if selected_items:
            self.hierarchy_tree.setCurrentItem(selected_items[0])
            for item in selected_items:
                item.setSelected(True)
            self.hierarchy_tree.scrollToItem(selected_items[0])

    def _reload_metric_choices(self, selected_metric_ids: set[object]) -> None:
        signal_blocker = QSignalBlocker(self.metric_list)
        self.metric_list.clear()
        selected_ids = {str(metric_id) for metric_id in selected_metric_ids}
        metric_ids = sorted(set(self.metrics) | selected_ids, key=str.casefold)
        for metric_id in metric_ids:
            metric = self.metrics.get(metric_id)
            if metric is None:
                item = QListWidgetItem(f"{metric_id} (метрика не найдена)")
                item.setForeground(MISSING_REFERENCE_BRUSH)
                item.setToolTip("Метрика не найдена в текущем комплексе")
            else:
                item = QListWidgetItem(f"{metric_id} ({metric['name']})")
            item.setData(Qt.ItemDataRole.UserRole, metric_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if metric_id in selected_ids
                else Qt.CheckState.Unchecked
            )
            self.metric_list.addItem(item)
        apply_metric_group_stripes(self.metric_list)
        del signal_blocker

    def _reload_include_choices(self, current_template_id: str | None) -> None:
        self.include_template_combo.clear()
        included_ids = {
            str(include["template_id"])
            for include in self.includes
        }
        for template_id in sorted(self.templates, key=str.casefold):
            if template_id == current_template_id or template_id in included_ids:
                continue
            template = self.templates[template_id]
            self.include_template_combo.addItem(
                f"{template_id} ({template['name']})",
                template_id,
            )
        self.add_include_button.setEnabled(
            self.include_template_combo.count() > 0
        )

    def _reload_include_list(self) -> None:
        signal_blocker = QSignalBlocker(self.include_list)
        self.include_list.clear()
        for include in self.includes:
            template_id = str(include["template_id"])
            if template_id in self.templates:
                item = QListWidgetItem(f"{template_id} × {include['count']}")
            else:
                item = QListWidgetItem(
                    f"{template_id} × {include['count']} (шаблон не найден)"
                )
                item.setForeground(MISSING_REFERENCE_BRUSH)
                item.setToolTip("Шаблон не найден в текущем комплексе")
            item.setData(Qt.ItemDataRole.UserRole, template_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked
                if include.get("join_target", False)
                else Qt.CheckState.Unchecked
            )
            self.include_list.addItem(item)
        del signal_blocker
        self.remove_include_button.setEnabled(False)

    def _include_target_changed(self, item: QListWidgetItem) -> None:
        template_id = str(item.data(Qt.ItemDataRole.UserRole))
        for include in self.includes:
            if include["template_id"] != template_id:
                continue
            if item.checkState() == Qt.CheckState.Checked:
                include["join_target"] = True
            else:
                include.pop("join_target", None)
            break
        self._reload_hierarchy()

    def _add_include(self) -> None:
        template_id = self.include_template_combo.currentData()
        if template_id is None:
            return
        self.includes.append({
            "count": self.include_count_spin.value(),
            "template_id": str(template_id),
        })
        self.include_count_spin.setValue(1)
        self._reload_include_list()
        self._reload_include_choices(self._selected_template_id())
        self._reload_hierarchy()

    def _remove_include(self) -> None:
        current_item = self.include_list.currentItem()
        if current_item is None:
            return
        template_id = str(current_item.data(Qt.ItemDataRole.UserRole))
        self.includes = [
            include
            for include in self.includes
            if include["template_id"] != template_id
        ]
        self._reload_include_list()
        self._reload_include_choices(self._selected_template_id())
        self._reload_hierarchy()

    def _sort_templates(self) -> None:
        if not self.unsaved.run(
            lambda: self._reload_templates(self._selected_template_id())
        ):
            with QSignalBlocker(self.sort_button):
                self.sort_button.setChecked(not self.sort_button.isChecked())

    def _delete_selected_template(self) -> None:
        template_id = self._selected_template_id()
        if template_id is None:
            return
        template_name = str(self.templates[template_id]["name"])
        answer = QMessageBox.question(
            self,
            "Удалить шаблон",
            f"Удалить шаблон «{template_name}» ({template_id})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_template(self.project_path, template_id)
        except InvalidTemplateError as error:
            QMessageBox.warning(self, "Не удалось удалить шаблон", str(error))
            return

        self._reload_templates()
        if self.template_list.count():
            self.template_list.setCurrentRow(0)
        else:
            self._new_template()

    def _selected_template_id(self) -> str | None:
        current_item = self.template_list.currentItem()
        if current_item is None:
            return None
        return str(current_item.data(Qt.ItemDataRole.UserRole))

    def _missing_references(
        self,
        template: dict[str, object],
    ) -> tuple[list[str], list[str]]:
        missing_metrics = sorted(
            (
                str(metric_id)
                for metric_id in template.get("metrics", [])
                if metric_id not in self.metrics
            ),
            key=str.casefold,
        )
        missing_templates = sorted(
            (
                str(include["template_id"])
                for include in template.get("includes", [])
                if include["template_id"] not in self.templates
            ),
            key=str.casefold,
        )
        return missing_metrics, missing_templates
