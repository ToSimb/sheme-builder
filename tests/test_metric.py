import json

import pytest

from scheme_builder.metric import (
    InvalidMetricError,
    load_metrics,
    normalize_metric,
    save_metric,
)


def test_normalize_metric_preserves_description():
    metric = {
        "metric_id": "cpu.temperature",
        "name": "Температура CPU",
        "description": "Температура процессора",
        "type": "double",
        "dimension": "°C",
        "query_interval": 10,
    }

    assert normalize_metric(metric) == metric


def test_normalize_metric_maps_legacy_comment_to_description():
    metric = {
        "metric_id": "cpu.temperature",
        "name": "Температура CPU",
        "comment": "Температура процессора",
        "type": "double",
        "dimension": "°C",
        "query_interval": 10,
    }

    normalized = normalize_metric(metric)

    assert normalized["description"] == "Температура процессора"
    assert "comment" not in normalized


def test_normalize_metric_rejects_conflicting_description_and_comment():
    metric = {
        "metric_id": "cpu.temperature",
        "description": "Новый текст",
        "comment": "Старый текст",
    }

    with pytest.raises(
        InvalidMetricError,
        match="разные значения полей description и comment",
    ):
        normalize_metric(metric)


@pytest.mark.parametrize(
    ("description", "comment"),
    [
        ("", "Старый текст"),
        ("Новый текст", ""),
    ],
)
def test_normalize_metric_rejects_conflict_with_empty_alias(
    description,
    comment,
):
    with pytest.raises(
        InvalidMetricError,
        match="разные значения полей description и comment",
    ):
        normalize_metric(
            {
                "description": description,
                "comment": comment,
            }
        )


def test_save_metric_writes_canonical_description(tmp_path):
    metric = {
        "metric_id": "cpu.temperature",
        "name": "Температура CPU",
        "comment": "Температура процессора",
        "type": "double",
        "dimension": "°C",
        "query_interval": 10,
    }

    metric_file = save_metric(tmp_path, metric)
    saved_metric = json.loads(metric_file.read_text(encoding="utf-8"))

    assert saved_metric["description"] == "Температура процессора"
    assert "comment" not in saved_metric


def test_load_metrics_normalizes_legacy_comment_without_rewriting_file(tmp_path):
    metrics_directory = tmp_path / "library" / "metrics"
    metrics_directory.mkdir(parents=True)
    metric_file = metrics_directory / "cpu.temperature.json"
    legacy_metric = {
        "metric_id": "cpu.temperature",
        "name": "Температура CPU",
        "comment": "Температура процессора",
        "type": "double",
        "dimension": "°C",
        "query_interval": 10,
    }
    metric_file.write_text(
        json.dumps(legacy_metric, ensure_ascii=False),
        encoding="utf-8",
    )

    loaded_metric = load_metrics(tmp_path)[0]

    assert loaded_metric["description"] == "Температура процессора"
    assert "comment" not in loaded_metric
    assert json.loads(metric_file.read_text(encoding="utf-8")) == legacy_metric


@pytest.mark.parametrize("field_name", ["description", "comment"])
@pytest.mark.parametrize("value", [42, None])
def test_normalize_metric_rejects_non_string_text_fields(field_name, value):
    with pytest.raises(
        InvalidMetricError,
        match="Поля description и comment должны быть строками",
    ):
        normalize_metric({field_name: value})
