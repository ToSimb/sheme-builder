import json

from scheme_builder.ui.metric_editor import MetricEditor


def test_editor_normalizes_legacy_comment_and_preserves_unknown_fields(
    qtbot,
    tmp_path,
):
    metrics_directory = tmp_path / "library" / "metrics"
    metrics_directory.mkdir(parents=True)
    metric_file = metrics_directory / "cpu.temperature.json"
    metric_file.write_text(
        json.dumps(
            {
                "metric_id": "cpu.temperature",
                "name": "Температура CPU",
                "comment": "Температура процессора",
                "type": "double",
                "dimension": "°C",
                "err_thr_min": 0,
                "err_thr_max": 90,
                "query_interval": 10,
                "source": {"kind": "fixture"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    editor = MetricEditor(tmp_path)
    qtbot.addWidget(editor)
    editor.metric_list.setCurrentRow(0)

    assert editor.description_edit.toPlainText() == "Температура процессора"
    editor.name_edit.setText("Температура процессора")
    editor.description_edit.clear()
    editor.err_thr_min_edit.clear()
    editor.err_thr_max_edit.clear()
    editor.save_button.click()

    saved_metric = json.loads(metric_file.read_text(encoding="utf-8"))
    assert saved_metric["source"] == {"kind": "fixture"}
    assert "description" not in saved_metric
    assert "comment" not in saved_metric
    assert "err_thr_min" not in saved_metric
    assert "err_thr_max" not in saved_metric
