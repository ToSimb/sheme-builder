import json

from scheme_builder.project import create_project


def test_create_project_creates_initial_structure(tmp_path):
    project_path = create_project(tmp_path, "test-complex")

    assert project_path == tmp_path / "test-complex"
    assert {path.name for path in project_path.iterdir()} == {
        "project.json",
        "metrics",
        "templates",
        "raw",
        "mapping",
        "proc",
        "exports",
    }
    assert json.loads((project_path / "project.json").read_text(encoding="utf-8")) == {
        "format_version": 1,
        "name": "test-complex",
    }
