import json
from pathlib import Path


class InvalidProjectError(ValueError):
    pass


def create_project(parent_directory: Path, name: str) -> Path:
    project_path = parent_directory / name
    project_path.mkdir(parents=True)

    for directory_name in (
        "metrics",
        "templates",
        "raw",
        "mapping",
        "proc",
        "exports",
    ):
        (project_path / directory_name).mkdir()

    project_data = {
        "format_version": 1,
        "name": name,
    }
    (project_path / "project.json").write_text(
        json.dumps(project_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return project_path


def open_project(project_path: Path) -> dict[str, int | str]:
    project_file = project_path / "project.json"
    if not project_file.is_file():
        raise InvalidProjectError("В выбранной папке нет файла project.json.")

    return json.loads(project_file.read_text(encoding="utf-8"))
