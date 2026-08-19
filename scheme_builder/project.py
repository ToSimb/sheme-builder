import json
from pathlib import Path

from scheme_builder.metric import InvalidMetricError, load_metrics


class InvalidProjectError(ValueError):
    pass


def create_project(parent_directory: Path, name: str) -> Path:
    project_path = parent_directory / name
    project_data = {
        "format_version": 1,
        "name": name,
    }
    try:
        project_path.mkdir(parents=True)
    except OSError as error:
        raise InvalidProjectError("Не удалось создать папку комплекса.") from error

    try:
        (project_path / "project.json").write_text(
            json.dumps(project_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (project_path / "metrics.json").write_text(
            json.dumps({"metrics": []}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeError) as error:
        for file_name in ("project.json", "metrics.json"):
            try:
                (project_path / file_name).unlink(missing_ok=True)
            except OSError:
                pass
        try:
            project_path.rmdir()
        except OSError:
            pass
        raise InvalidProjectError("Не удалось создать файлы комплекса.") from error

    return project_path


def open_project(project_path: Path) -> dict[str, int | str]:
    project_file = project_path / "project.json"
    if not project_file.is_file():
        raise InvalidProjectError("В выбранной папке нет файла project.json.")

    try:
        project_text = project_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InvalidProjectError("Не удалось прочитать файлы комплекса.") from error

    try:
        project_data = json.loads(project_text)
    except json.JSONDecodeError as error:
        raise InvalidProjectError(
            "Файлы комплекса содержат некорректные данные."
        ) from error

    if (
        not isinstance(project_data, dict)
        or type(project_data.get("format_version")) is not int
        or project_data["format_version"] != 1
        or not isinstance(project_data.get("name"), str)
        or not project_data["name"]
    ):
        raise InvalidProjectError("Файл project.json имеет неверную структуру.")

    try:
        load_metrics(project_path)
    except InvalidMetricError as error:
        raise InvalidProjectError(str(error)) from error

    return project_data
