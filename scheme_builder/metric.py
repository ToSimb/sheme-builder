import json
import math
import re
from pathlib import Path

from scheme_builder.config import (
    MAX_QUERY_INTERVAL,
    METRIC_TYPES,
    MIN_QUERY_INTERVAL,
)

METRIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.]+$")
METRICS_FILE_NAME = "metrics.json"


class InvalidMetricError(ValueError):
    pass


def normalize_metric(metric: dict[str, object]) -> dict[str, object]:
    normalized = dict(metric)
    has_description = "description" in normalized
    has_comment = "comment" in normalized
    description = normalized.get("description")
    comment = normalized.get("comment")
    if any(
        field_name in normalized and not isinstance(normalized[field_name], str)
        for field_name in ("description", "comment")
    ):
        raise InvalidMetricError(
            "Поля description и comment должны быть строками."
        )
    if has_description and has_comment and description != comment:
        raise InvalidMetricError(
            "Метрика содержит разные значения полей description и comment."
        )
    if not has_description and has_comment:
        normalized["description"] = comment
    normalized.pop("comment", None)
    if not normalized.get("description") and isinstance(normalized.get("name"), str):
        normalized["description"] = normalized["name"]
    return normalized


def _validate_metric(metric: dict[str, object]) -> dict[str, object]:
    metric = normalize_metric(metric)
    metric_id = metric.get("metric_id")
    if not isinstance(metric_id, str) or not METRIC_ID_PATTERN.fullmatch(metric_id):
        raise InvalidMetricError(
            "metric_id должен содержать только латинские буквы, цифры, '_' и '.'."
        )
    if not isinstance(metric.get("name"), str) or not metric["name"]:
        raise InvalidMetricError("Название метрики не должно быть пустым.")
    if not isinstance(metric.get("description"), str) or not metric["description"]:
        raise InvalidMetricError("Описание метрики не должно быть пустым.")
    if metric.get("type") not in METRIC_TYPES:
        raise InvalidMetricError("Указан неподдерживаемый тип метрики.")
    if not isinstance(metric.get("dimension"), str) or not metric["dimension"]:
        raise InvalidMetricError("Единица измерения не должна быть пустой.")
    if metric["type"] in ("string", "state") and metric["dimension"] != "none":
        raise InvalidMetricError(
            "Для типов string и state единица измерения должна быть none."
        )

    query_interval = metric.get("query_interval")
    if (
        type(query_interval) is not int
        or not MIN_QUERY_INTERVAL <= query_interval <= MAX_QUERY_INTERVAL
    ):
        raise InvalidMetricError(
            "Период опроса должен быть от "
            f"{MIN_QUERY_INTERVAL} до {MAX_QUERY_INTERVAL} секунд."
        )

    if "is_config" in metric and type(metric["is_config"]) is not bool:
        raise InvalidMetricError("Поле is_config должно быть логическим значением.")
    if metric.get("is_config") is False:
        metric.pop("is_config")

    has_threshold = False
    for field_name in ("err_thr_min", "err_thr_max"):
        if field_name not in metric:
            continue
        has_threshold = True
        value = metric[field_name]
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or isinstance(value, float) and not math.isfinite(value)
        ):
            raise InvalidMetricError("Границы метрики должны быть конечными числами.")

    if has_threshold and metric["type"] not in ("integer", "double"):
        raise InvalidMetricError(
            "Границы можно задавать только для типов integer и double."
        )
    if (
        "err_thr_min" in metric
        and "err_thr_max" in metric
        and metric["err_thr_min"] > metric["err_thr_max"]
    ):
        raise InvalidMetricError(
            "Нижняя граница не должна быть больше верхней."
        )

    return metric


def _write_metrics(project_path: Path, metrics: list[dict[str, object]]) -> Path:
    metric_file = project_path / METRICS_FILE_NAME
    temporary_file = metric_file.with_name(metric_file.name + ".tmp")
    try:
        temporary_file.write_text(
            json.dumps({"metrics": metrics}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_file.replace(metric_file)
    except (OSError, UnicodeError, TypeError, ValueError) as error:
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass
        raise InvalidMetricError("Не удалось записать файл metrics.json.") from error
    return metric_file


def save_metric(project_path: Path, metric: dict[str, object]) -> Path:
    metric = _validate_metric(metric)
    metric_id = metric["metric_id"]

    metrics = load_metrics(project_path)
    for index, existing_metric in enumerate(metrics):
        if existing_metric["metric_id"] == metric_id:
            metrics[index] = metric
            break
    else:
        metrics.append(metric)

    return _write_metrics(project_path, metrics)


def delete_metric(project_path: Path, metric_id: str) -> Path:
    metrics = load_metrics(project_path)
    remaining_metrics = [
        metric for metric in metrics if metric["metric_id"] != metric_id
    ]
    if len(remaining_metrics) == len(metrics):
        raise InvalidMetricError(f"Метрика '{metric_id}' не найдена.")
    return _write_metrics(project_path, remaining_metrics)


def load_metrics(project_path: Path) -> list[dict[str, object]]:
    metric_file = project_path / METRICS_FILE_NAME
    if not metric_file.is_file():
        raise InvalidMetricError("В комплексе нет файла metrics.json.")

    try:
        metric_text = metric_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InvalidMetricError("Не удалось прочитать файл metrics.json.") from error

    try:
        document = json.loads(metric_text)
    except json.JSONDecodeError as error:
        raise InvalidMetricError("Файл metrics.json содержит некорректный JSON.") from error

    if not isinstance(document, dict) or not isinstance(document.get("metrics"), list):
        raise InvalidMetricError(
            "Файл metrics.json должен содержать объект с массивом metrics."
        )

    metrics: list[dict[str, object]] = []
    metric_ids: set[str] = set()
    for metric in document["metrics"]:
        if not isinstance(metric, dict):
            raise InvalidMetricError("Каждая метрика должна быть JSON-объектом.")
        normalized_metric = _validate_metric(metric)
        metric_id = normalized_metric["metric_id"]
        if metric_id in metric_ids:
            raise InvalidMetricError(f"metric_id '{metric_id}' встречается несколько раз.")
        metric_ids.add(metric_id)
        metrics.append(normalized_metric)

    return metrics
