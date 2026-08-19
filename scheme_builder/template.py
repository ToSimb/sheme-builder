import json
import re
from pathlib import Path

TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.]+$")
TEMPLATES_FILE_NAME = "templates.json"
_TEMPLATE_FIELDS = {"template_id", "name", "description", "metrics", "includes"}
_INCLUDE_FIELDS = {"count", "template_id"}


class InvalidTemplateError(ValueError):
    pass


def _validate_template_shape(template: dict[str, object]) -> dict[str, object]:
    normalized = dict(template)
    unknown_fields = set(normalized) - _TEMPLATE_FIELDS
    if unknown_fields:
        raise InvalidTemplateError(
            "Шаблон содержит неподдерживаемые поля: "
            + ", ".join(sorted(unknown_fields))
            + "."
        )

    template_id = normalized.get("template_id")
    if (
        not isinstance(template_id, str)
        or not TEMPLATE_ID_PATTERN.fullmatch(template_id)
    ):
        raise InvalidTemplateError(
            "template_id должен содержать только латинские буквы, цифры, '_' и '.'."
        )

    name = normalized.get("name")
    if not isinstance(name, str) or not name:
        raise InvalidTemplateError("Название шаблона не должно быть пустым.")

    description = normalized.get("description")
    if description == "" or description is None:
        normalized["description"] = name
    elif not isinstance(description, str):
        raise InvalidTemplateError("Описание шаблона должно быть строкой.")

    metrics = normalized.get("metrics", [])
    if not isinstance(metrics, list) or any(
        not isinstance(metric_id, str) or not metric_id for metric_id in metrics
    ):
        raise InvalidTemplateError("Поле metrics должно быть списком metric_id.")
    if len(set(metrics)) != len(metrics):
        raise InvalidTemplateError("Метрика не должна повторяться в одном шаблоне.")
    if metrics:
        normalized["metrics"] = list(metrics)
    else:
        normalized.pop("metrics", None)

    includes = normalized.get("includes", [])
    if not isinstance(includes, list):
        raise InvalidTemplateError("Поле includes должно быть списком.")

    normalized_includes: list[dict[str, int | str]] = []
    included_ids: set[str] = set()
    for include in includes:
        if not isinstance(include, dict) or set(include) != _INCLUDE_FIELDS:
            raise InvalidTemplateError(
                "Каждое включение должно содержать только template_id и count."
            )
        included_template_id = include.get("template_id")
        count = include.get("count")
        if (
            not isinstance(included_template_id, str)
            or not TEMPLATE_ID_PATTERN.fullmatch(included_template_id)
        ):
            raise InvalidTemplateError("Включение содержит неверный template_id.")
        if type(count) is not int or count <= 0:
            raise InvalidTemplateError(
                "Количество включений должно быть целым числом больше нуля."
            )
        if included_template_id in included_ids:
            raise InvalidTemplateError(
                "Дочерний шаблон не должен повторяться в одном шаблоне."
            )
        included_ids.add(included_template_id)
        normalized_includes.append({
            "count": count,
            "template_id": included_template_id,
        })

    if normalized_includes:
        normalized["includes"] = normalized_includes
    else:
        normalized.pop("includes", None)

    return normalized


def _validate_template_catalog(
    templates: list[dict[str, object]],
) -> list[dict[str, object]]:
    normalized_templates: list[dict[str, object]] = []
    templates_by_id: dict[str, dict[str, object]] = {}
    for template in templates:
        normalized = _validate_template_shape(template)
        template_id = str(normalized["template_id"])
        if template_id in templates_by_id:
            raise InvalidTemplateError(
                f"template_id '{template_id}' встречается несколько раз."
            )
        templates_by_id[template_id] = normalized
        normalized_templates.append(normalized)

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(template_id: str) -> None:
        if template_id in visiting:
            raise InvalidTemplateError("Включения шаблонов образуют цикл.")
        if template_id in visited:
            return
        visiting.add(template_id)
        for include in templates_by_id[template_id].get("includes", []):
            included_template_id = str(include["template_id"])
            if included_template_id in templates_by_id:
                visit(included_template_id)
        visiting.remove(template_id)
        visited.add(template_id)

    for template_id in templates_by_id:
        visit(template_id)

    return normalized_templates


def _write_templates(
    project_path: Path,
    templates: list[dict[str, object]],
) -> Path:
    template_file = project_path / TEMPLATES_FILE_NAME
    temporary_file = template_file.with_name(template_file.name + ".tmp")
    try:
        temporary_file.write_text(
            json.dumps({"templates": templates}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_file.replace(template_file)
    except (OSError, UnicodeError, TypeError, ValueError) as error:
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass
        raise InvalidTemplateError(
            "Не удалось записать файл templates.json."
        ) from error
    return template_file


def load_templates(project_path: Path) -> list[dict[str, object]]:
    template_file = project_path / TEMPLATES_FILE_NAME
    if not template_file.is_file():
        return []

    try:
        template_text = template_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise InvalidTemplateError(
            "Не удалось прочитать файл templates.json."
        ) from error

    try:
        document = json.loads(template_text)
    except json.JSONDecodeError as error:
        raise InvalidTemplateError(
            "Файл templates.json содержит некорректный JSON."
        ) from error

    if not isinstance(document, dict) or not isinstance(
        document.get("templates"),
        list,
    ):
        raise InvalidTemplateError(
            "Файл templates.json должен содержать объект с массивом templates."
        )
    if any(not isinstance(template, dict) for template in document["templates"]):
        raise InvalidTemplateError("Каждый шаблон должен быть JSON-объектом.")

    return _validate_template_catalog(document["templates"])


def save_template(project_path: Path, template: dict[str, object]) -> Path:
    normalized = _validate_template_shape(template)
    template_id = normalized["template_id"]
    templates = load_templates(project_path)
    for index, existing_template in enumerate(templates):
        if existing_template["template_id"] == template_id:
            templates[index] = normalized
            break
    else:
        templates.append(normalized)

    templates = _validate_template_catalog(templates)
    return _write_templates(project_path, templates)


def delete_template(project_path: Path, template_id: str) -> Path:
    templates = load_templates(project_path)
    if not any(template["template_id"] == template_id for template in templates):
        raise InvalidTemplateError(f"Шаблон '{template_id}' не найден.")

    for template in templates:
        for include in template.get("includes", []):
            if include["template_id"] == template_id:
                raise InvalidTemplateError(
                    f"Шаблон используется в '{template['template_id']}' "
                    "и не может быть удалён."
                )

    remaining_templates = [
        template for template in templates if template["template_id"] != template_id
    ]
    remaining_templates = _validate_template_catalog(remaining_templates)
    return _write_templates(project_path, remaining_templates)
