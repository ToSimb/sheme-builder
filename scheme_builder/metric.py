import json
import re
from pathlib import Path

METRIC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.]+$")
METRIC_TYPES = ("string", "integer", "double", "state")


class InvalidMetricError(ValueError):
    pass


def save_metric(project_path: Path, metric: dict[str, object]) -> Path:
    metric_id = metric.get("metric_id")
    if not isinstance(metric_id, str) or not METRIC_ID_PATTERN.fullmatch(metric_id):
        raise InvalidMetricError(
            "metric_id должен содержать только латинские буквы, цифры, '_' и '.'."
        )
    if not isinstance(metric.get("name"), str) or not metric["name"]:
        raise InvalidMetricError("Название метрики не должно быть пустым.")
    if metric.get("type") not in METRIC_TYPES:
        raise InvalidMetricError("Указан неподдерживаемый тип метрики.")
    if not isinstance(metric.get("dimension"), str) or not metric["dimension"]:
        raise InvalidMetricError("Единица измерения не должна быть пустой.")

    query_interval = metric.get("query_interval")
    if not isinstance(query_interval, int) or not 1 <= query_interval <= 600:
        raise InvalidMetricError("Период опроса должен быть от 1 до 600 секунд.")

    metrics_directory = project_path / "library" / "metrics"
    metrics_directory.mkdir(parents=True, exist_ok=True)
    metric_file = metrics_directory / f"{metric_id}.json"
    temporary_file = metric_file.with_name(metric_file.name + ".tmp")
    temporary_file.write_text(
        json.dumps(metric, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_file.replace(metric_file)
    return metric_file


def load_metrics(project_path: Path) -> list[dict[str, object]]:
    metrics_directory = project_path / "library" / "metrics"
    metrics = [
        json.loads(metric_file.read_text(encoding="utf-8"))
        for metric_file in metrics_directory.glob("*.json")
    ]
    return sorted(metrics, key=lambda metric: str(metric["metric_id"]))
