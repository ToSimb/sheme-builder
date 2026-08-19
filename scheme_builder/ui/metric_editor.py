from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
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
    DEFAULT_QUERY_INTERVAL,
    MAX_QUERY_INTERVAL,
    METRIC_DIMENSIONS,
    METRIC_TYPES,
    MIN_QUERY_INTERVAL,
)
from scheme_builder.metric import (
    InvalidMetricError,
    delete_metric,
    load_metrics,
    save_metric,
)


class MetricEditor(QWidget):
    def __init__(self, project_path: Path, parent: QWidget | None = None):
        super().__init__(parent)
        self.project_path = project_path
        self.metrics: dict[str, dict[str, object]] = {}

        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        list_panel = QWidget(splitter)
        list_layout = QVBoxLayout(list_panel)
        self.metric_list = QListWidget(list_panel)
        self.metric_list.setObjectName("metricList")
        self.new_button = QPushButton("Создать метрику", list_panel)
        self.new_button.setObjectName("newMetricButton")
        self.sort_button = QPushButton("Сортировать по metric_id", list_panel)
        self.sort_button.setObjectName("sortMetricsButton")
        self.sort_button.setCheckable(True)
        self.delete_button = QPushButton("Удалить метрику", list_panel)
        self.delete_button.setObjectName("deleteMetricButton")
        self.delete_button.setEnabled(False)
        list_layout.addWidget(self.metric_list)
        list_layout.addWidget(self.new_button)
        list_layout.addWidget(self.sort_button)
        list_layout.addWidget(self.delete_button)

        scroll_area = QScrollArea(splitter)
        scroll_area.setWidgetResizable(True)
        form_panel = QWidget()
        form_layout = QVBoxLayout(form_panel)
        fields_layout = QFormLayout()

        self.metric_id_edit = QLineEdit()
        self.metric_id_edit.setObjectName("metricIdEdit")
        fields_layout.addRow("Идентификатор:", self.metric_id_edit)

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("metricNameEdit")
        fields_layout.addRow("Название:", self.name_edit)

        self.description_edit = QPlainTextEdit()
        self.description_edit.setObjectName("metricDescriptionEdit")
        self.description_edit.setMaximumHeight(90)
        fields_layout.addRow("Описание:", self.description_edit)

        self.type_combo = QComboBox()
        self.type_combo.setObjectName("metricTypeCombo")
        self.type_combo.addItems(METRIC_TYPES)
        fields_layout.addRow("Тип:", self.type_combo)

        self.is_config_check = QCheckBox("Конфигурационная метрика")
        self.is_config_check.setObjectName("metricIsConfigCheck")
        fields_layout.addRow("", self.is_config_check)

        self.dimension_combo = QComboBox()
        self.dimension_combo.setObjectName("metricDimensionCombo")
        self.dimension_combo.addItems(METRIC_DIMENSIONS)
        fields_layout.addRow("Единица измерения:", self.dimension_combo)

        self.err_thr_min_edit = QLineEdit()
        self.err_thr_min_edit.setObjectName("metricErrThrMinEdit")
        self.err_thr_min_edit.setPlaceholderText("Не задано")
        fields_layout.addRow("Нижняя граница:", self.err_thr_min_edit)

        self.err_thr_max_edit = QLineEdit()
        self.err_thr_max_edit.setObjectName("metricErrThrMaxEdit")
        self.err_thr_max_edit.setPlaceholderText("Не задано")
        fields_layout.addRow("Верхняя граница:", self.err_thr_max_edit)

        self.query_interval_spin = QSpinBox()
        self.query_interval_spin.setObjectName("metricQueryIntervalSpin")
        self.query_interval_spin.setRange(MIN_QUERY_INTERVAL, MAX_QUERY_INTERVAL)
        self.query_interval_spin.setSuffix(" с")
        fields_layout.addRow("Период опроса:", self.query_interval_spin)

        self.save_button = QPushButton("Сохранить", form_panel)
        self.save_button.setObjectName("saveMetricButton")
        form_layout.addLayout(fields_layout)
        form_layout.addWidget(self.save_button)
        form_layout.addStretch()
        scroll_area.setWidget(form_panel)

        splitter.addWidget(list_panel)
        splitter.addWidget(scroll_area)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout = QVBoxLayout(self)
        layout.addWidget(splitter)

        self.new_button.clicked.connect(self._new_metric)
        self.sort_button.toggled.connect(self._sort_metrics)
        self.delete_button.clicked.connect(self._delete_selected_metric)
        self.save_button.clicked.connect(self._save_metric)
        self.metric_list.currentItemChanged.connect(self._selection_changed)
        self.type_combo.currentTextChanged.connect(self._update_type_fields)

        self._reload_metrics()
        if self.metric_list.count() == 0:
            self._new_metric()

    def _new_metric(self) -> None:
        self.metric_list.setCurrentRow(-1)
        self.metric_id_edit.setEnabled(True)
        self.metric_id_edit.clear()
        self.name_edit.clear()
        self.description_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.is_config_check.setChecked(False)
        self.dimension_combo.setCurrentText("none")
        self.err_thr_min_edit.clear()
        self.err_thr_max_edit.clear()
        self.query_interval_spin.setValue(DEFAULT_QUERY_INTERVAL)
        self._update_type_fields(self.type_combo.currentText())
        self.metric_id_edit.setFocus()

    def _save_metric(self) -> None:
        try:
            metric = self._collect_metric()
            save_metric(self.project_path, metric)
        except (InvalidMetricError, ValueError) as error:
            QMessageBox.warning(self, "Не удалось сохранить метрику", str(error))
            return

        self._reload_metrics(selected_metric_id=str(metric["metric_id"]))

    def _collect_metric(self) -> dict[str, object]:
        metric_id = self.metric_id_edit.text().strip()
        metric = (
            dict(self.metrics.get(metric_id, {}))
            if not self.metric_id_edit.isEnabled()
            else {}
        )
        name = self.name_edit.text().strip()
        metric_type = self.type_combo.currentText()
        metric.update({
            "metric_id": metric_id,
            "name": name,
            "type": metric_type,
            "dimension": self.dimension_combo.currentText(),
            "description": self.description_edit.toPlainText().strip() or name,
            "query_interval": self.query_interval_spin.value(),
        })

        if self.is_config_check.isChecked():
            metric["is_config"] = True
        else:
            metric.pop("is_config", None)
        metric.pop("comment", None)

        for field_name, field in (
            ("err_thr_min", self.err_thr_min_edit),
            ("err_thr_max", self.err_thr_max_edit),
        ):
            value = (
                field.text().strip()
                if metric_type in ("integer", "double")
                else ""
            )
            if value:
                try:
                    metric[field_name] = float(value.replace(",", "."))
                except ValueError as error:
                    raise InvalidMetricError(
                        "Границы должны быть числами или оставаться пустыми."
                    ) from error
            else:
                metric.pop(field_name, None)

        return metric

    def _reload_metrics(self, selected_metric_id: str | None = None) -> None:
        self.metrics = {
            str(metric["metric_id"]): metric
            for metric in load_metrics(self.project_path)
        }
        signal_blocker = QSignalBlocker(self.metric_list)
        self.metric_list.clear()
        metric_ids = list(self.metrics)
        if self.sort_button.isChecked():
            metric_ids.sort(key=str.casefold)

        for metric_id in metric_ids:
            metric = self.metrics[metric_id]
            item = QListWidgetItem(f"{metric_id} ({metric['name']})")
            item.setData(Qt.ItemDataRole.UserRole, metric_id)
            item.setToolTip(metric_id)
            self.metric_list.addItem(item)

        selected_item = None
        if selected_metric_id is not None:
            for row in range(self.metric_list.count()):
                item = self.metric_list.item(row)
                if item.data(Qt.ItemDataRole.UserRole) == selected_metric_id:
                    selected_item = item
                    break
        del signal_blocker

        self.delete_button.setEnabled(False)
        if selected_item is not None:
            self.metric_list.setCurrentItem(selected_item)

    def _selection_changed(
        self,
        current_item: QListWidgetItem | None,
        previous_item: QListWidgetItem | None,
    ) -> None:
        del previous_item
        self.delete_button.setEnabled(current_item is not None)
        if current_item is not None:
            metric_id = str(current_item.data(Qt.ItemDataRole.UserRole))
            if metric_id in self.metrics:
                self._load_selected_metric(metric_id)

    def _sort_metrics(self) -> None:
        self._reload_metrics(self._selected_metric_id())

    def _delete_selected_metric(self) -> None:
        metric_id = self._selected_metric_id()
        if metric_id is None:
            return

        metric_name = str(self.metrics[metric_id]["name"])
        answer = QMessageBox.question(
            self,
            "Удалить метрику",
            f"Удалить метрику «{metric_name}» ({metric_id})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_metric(self.project_path, metric_id)
        except InvalidMetricError as error:
            QMessageBox.warning(self, "Не удалось удалить метрику", str(error))
            return

        self._reload_metrics()
        if self.metric_list.count():
            self.metric_list.setCurrentRow(0)
        else:
            self._new_metric()

    def _selected_metric_id(self) -> str | None:
        current_item = self.metric_list.currentItem()
        if current_item is None:
            return None
        return str(current_item.data(Qt.ItemDataRole.UserRole))

    def _load_selected_metric(self, metric_id: str) -> None:
        if not metric_id:
            return

        metric = self.metrics[metric_id]
        self.metric_id_edit.setText(metric_id)
        self.metric_id_edit.setEnabled(False)
        self.name_edit.setText(str(metric["name"]))
        self.description_edit.setPlainText(str(metric.get("description", "")))
        self.type_combo.setCurrentText(str(metric["type"]))
        self.is_config_check.setChecked(bool(metric.get("is_config", False)))
        dimension = str(metric["dimension"])
        if self.dimension_combo.findText(dimension) == -1:
            self.dimension_combo.addItem(dimension)
        self.dimension_combo.setCurrentText(dimension)
        self.err_thr_min_edit.setText(self._optional_number(metric.get("err_thr_min")))
        self.err_thr_max_edit.setText(self._optional_number(metric.get("err_thr_max")))
        self.query_interval_spin.setValue(int(metric["query_interval"]))
        self._update_type_fields(self.type_combo.currentText())

    def _update_type_fields(self, metric_type: str) -> None:
        dimension_is_fixed = metric_type in ("string", "state")
        if dimension_is_fixed:
            self.dimension_combo.setCurrentText("none")
        self.dimension_combo.setEnabled(not dimension_is_fixed)

        thresholds_enabled = metric_type in ("integer", "double")
        self.err_thr_min_edit.setEnabled(thresholds_enabled)
        self.err_thr_max_edit.setEnabled(thresholds_enabled)

    @staticmethod
    def _optional_number(value: object) -> str:
        return "" if value is None else str(value)
