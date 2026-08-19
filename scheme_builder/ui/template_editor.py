from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
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
    QVBoxLayout,
    QWidget,
)

from scheme_builder.config import (
    CATALOG_LIST_WIDTH,
    TEMPLATE_METRIC_LIST_MIN_HEIGHT,
)
from scheme_builder.metric import InvalidMetricError, load_metrics
from scheme_builder.template import (
    InvalidTemplateError,
    delete_template,
    load_templates,
    save_template,
)
from scheme_builder.ui.metric_list import apply_metric_group_stripes

MISSING_REFERENCE_BRUSH = QBrush(QColor("#c62828"))


class TemplateEditor(QWidget):
    def __init__(self, project_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.project_path = project_path
        self.metrics: dict[str, dict[str, object]] = {}
        self.templates: dict[str, dict[str, object]] = {}
        self.includes: list[dict[str, int | str]] = []

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        list_panel = QWidget(splitter)
        list_panel.setMinimumWidth(CATALOG_LIST_WIDTH)
        list_layout = QVBoxLayout(list_panel)
        self.template_list = QListWidget(list_panel)
        self.template_list.setObjectName("templateList")
        self.new_button = QPushButton("Создать шаблон", list_panel)
        self.new_button.setObjectName("newTemplateButton")
        self.sort_button = QPushButton("Сортировать по template_id", list_panel)
        self.sort_button.setObjectName("sortTemplatesButton")
        self.sort_button.setCheckable(True)
        self.delete_button = QPushButton("Удалить шаблон", list_panel)
        self.delete_button.setObjectName("deleteTemplateButton")
        self.delete_button.setEnabled(False)
        list_layout.addWidget(self.template_list)
        list_layout.addWidget(self.new_button)
        list_layout.addWidget(self.sort_button)
        list_layout.addWidget(self.delete_button)

        scroll_area = QScrollArea(splitter)
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
        form_layout.addWidget(QLabel("Дочерние шаблоны:"))
        form_layout.addLayout(include_controls)
        form_layout.addWidget(self.include_list)
        form_layout.addWidget(self.remove_include_button)
        form_layout.addWidget(self.save_button)
        form_layout.addStretch()
        scroll_area.setWidget(form_panel)

        splitter.addWidget(list_panel)
        splitter.addWidget(scroll_area)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self.new_button.clicked.connect(self._new_template)
        self.sort_button.toggled.connect(self._sort_templates)
        self.delete_button.clicked.connect(self._delete_selected_template)
        self.save_button.clicked.connect(self._save_template)
        self.template_list.currentItemChanged.connect(self._selection_changed)
        self.add_include_button.clicked.connect(self._add_include)
        self.remove_include_button.clicked.connect(self._remove_include)
        self.include_list.currentItemChanged.connect(
            lambda current, previous: self.remove_include_button.setEnabled(
                current is not None
            )
        )

        self._reload_templates()
        if self.template_list.count() == 0:
            self._new_template()

    def refresh(self) -> None:
        self._reload_templates(self._selected_template_id())

    def _new_template(self) -> None:
        self.template_list.setCurrentRow(-1)
        self.template_id_edit.setEnabled(True)
        self.template_id_edit.clear()
        self.name_edit.clear()
        self.description_edit.clear()
        self.includes = []
        self._reload_metric_choices(set())
        self._reload_include_list()
        self._reload_include_choices(None)
        self.template_id_edit.setFocus()

    def _save_template(self) -> None:
        try:
            template = self._collect_template()
            save_template(self.project_path, template)
        except (InvalidMetricError, InvalidTemplateError) as error:
            QMessageBox.warning(self, "Не удалось сохранить шаблон", str(error))
            return

        self._reload_templates(selected_template_id=str(template["template_id"]))

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
        signal_blocker = QSignalBlocker(self.template_list)
        self.template_list.clear()
        template_ids = list(self.templates)
        if self.sort_button.isChecked():
            template_ids.sort(key=str.casefold)

        selected_item = None
        for template_id in template_ids:
            template = self.templates[template_id]
            item = QListWidgetItem(f"{template_id} ({template['name']})")
            item.setData(Qt.ItemDataRole.UserRole, template_id)
            missing_metrics, missing_templates = self._missing_references(template)
            if missing_metrics or missing_templates:
                item.setForeground(MISSING_REFERENCE_BRUSH)
                missing_parts = []
                if missing_metrics:
                    missing_parts.append("метрики: " + ", ".join(missing_metrics))
                if missing_templates:
                    missing_parts.append(
                        "шаблоны: " + ", ".join(missing_templates)
                    )
                item.setToolTip("Не найдены " + "; ".join(missing_parts))
            else:
                item.setToolTip(template_id)
            self.template_list.addItem(item)
            if template_id == selected_template_id:
                selected_item = item
        del signal_blocker

        self.delete_button.setEnabled(False)
        if selected_item is not None:
            self.template_list.setCurrentItem(selected_item)
        else:
            self._reload_include_choices(None)

    def _selection_changed(
        self,
        current_item: QListWidgetItem | None,
        previous_item: QListWidgetItem | None,
    ) -> None:
        del previous_item
        self.delete_button.setEnabled(current_item is not None)
        if current_item is None:
            return
        template_id = str(current_item.data(Qt.ItemDataRole.UserRole))
        if template_id in self.templates:
            self._load_selected_template(template_id)

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
            self.include_list.addItem(item)
        self.remove_include_button.setEnabled(False)

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

    def _sort_templates(self) -> None:
        self._reload_templates(self._selected_template_id())

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
