import json

from scheme_builder.project import create_project


def test_create_project_creates_initial_structure(tmp_path):
    project_path = create_project(tmp_path, "test-complex")

    assert project_path == tmp_path / "test-complex"
    assert {path.name for path in project_path.iterdir()} == {
        "project.json",
        "library",
        "agents",
        "join",
        "exports",
    }
    assert {
        path.relative_to(project_path).as_posix()
        for path in project_path.rglob("*")
        if path.is_dir()
    } == {
        "library",
        "library/metrics",
        "library/templates",
        "agents",
        "join",
        "exports",
        "exports/agents",
    }
    assert json.loads((project_path / "project.json").read_text(encoding="utf-8")) == {
        "format_version": 1,
        "name": "test-complex",
    }
