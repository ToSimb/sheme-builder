from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from scheme_builder.metric import (
    METRIC_TYPES,
    InvalidMetricError,
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
        list_layout.addWidget(self.metric_list)
        list_layout.addWidget(self.new_button)

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

        self.dimension_edit = QLineEdit()
        self.dimension_edit.setObjectName("metricDimensionEdit")
        fields_layout.addRow("Единица измерения:", self.dimension_edit)

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
        self.query_interval_spin.setRange(1, 600)
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
        self.save_button.clicked.connect(self._save_metric)
        self.metric_list.currentTextChanged.connect(self._load_selected_metric)

        self._reload_metrics()
        if self.metric_list.count() == 0:
            self._new_metric()

    def _new_metric(self) -> None:
        self.metric_list.clearSelection()
        self.metric_id_edit.setEnabled(True)
        self.metric_id_edit.clear()
        self.name_edit.clear()
        self.description_edit.clear()
        self.type_combo.setCurrentIndex(0)
        self.is_config_check.setChecked(False)
        self.dimension_edit.clear()
        self.err_thr_min_edit.clear()
        self.err_thr_max_edit.clear()
        self.query_interval_spin.setValue(10)
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
        metric.update({
            "metric_id": metric_id,
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentText(),
            "is_config": self.is_config_check.isChecked(),
            "dimension": self.dimension_edit.text().strip(),
            "query_interval": self.query_interval_spin.value(),
        })

        description = self.description_edit.toPlainText().strip()
        if description:
            metric["description"] = description
        else:
            metric.pop("description", None)
        metric.pop("comment", None)

        for field_name, field in (
            ("err_thr_min", self.err_thr_min_edit),
            ("err_thr_max", self.err_thr_max_edit),
        ):
            value = field.text().strip()
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
        self.metric_list.clear()
        self.metric_list.addItems(self.metrics)

        if selected_metric_id is not None:
            matching_items = self.metric_list.findItems(
                selected_metric_id,
                Qt.MatchFlag.MatchExactly,
            )
            if matching_items:
                self.metric_list.setCurrentItem(matching_items[0])

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
        self.dimension_edit.setText(str(metric["dimension"]))
        self.err_thr_min_edit.setText(self._optional_number(metric.get("err_thr_min")))
        self.err_thr_max_edit.setText(self._optional_number(metric.get("err_thr_max")))
        self.query_interval_spin.setValue(int(metric["query_interval"]))

    @staticmethod
    def _optional_number(value: object) -> str:
        return "" if value is None else str(value)
