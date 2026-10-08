import json
import re
from pathlib import Path
from tempfile import NamedTemporaryFile

from scheme_builder.metric import load_metrics
from scheme_builder.template import load_templates, template_for_transport

AGENT_SCHEME_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.]+$")
AGENT_SCHEMES_FILE_NAME = "agent_schemes.json"
MAX_AGENT_ITEMS = 100_000
_AGENT_SCHEME_FIELDS = {"agent_scheme_id", "name", "description", "roots"}
_ROOT_FIELDS = {"count", "template_id"}


class InvalidAgentSchemeError(ValueError):
    pass


def _validate_agent_scheme(agent_scheme: dict[str, object]) -> dict[str, object]:
    normalized = dict(agent_scheme)
    unknown_fields = set(normalized) - _AGENT_SCHEME_FIELDS
    if unknown_fields:
        raise InvalidAgentSchemeError(
            "AgentScheme содержит неподдерживаемые поля: "
            + ", ".join(sorted(unknown_fields))
            + "."
        )

    agent_scheme_id = normalized.get("agent_scheme_id")
    if (
        not isinstance(agent_scheme_id, str)
        or not AGENT_SCHEME_ID_PATTERN.fullmatch(agent_scheme_id)
    ):
        raise InvalidAgentSchemeError(
            "agent_scheme_id должен содержать только латинские буквы, цифры, '_' и '.'."
        )

    name = normalized.get("name")
    if not isinstance(name, str) or not name:
        raise InvalidAgentSchemeError("Название AgentScheme не должно быть пустым.")

    description = normalized.get("description")
    if description == "" or description is None:
        normalized["description"] = name
    elif not isinstance(description, str):
        raise InvalidAgentSchemeError("Описание AgentScheme должно быть строкой.")

    roots = normalized.get("roots")
    if not isinstance(roots, list) or not roots:
        raise InvalidAgentSchemeError(
            "AgentScheme должна содержать хотя бы один корневой шаблон."
        )

    normalized_roots: list[dict[str, int | str]] = []
    root_template_ids: set[str] = set()
    for root in roots:
        if not isinstance(root, dict) or set(root) != _ROOT_FIELDS:
            raise InvalidAgentSchemeError(
                "Каждый корень должен содержать только template_id и count."
            )
        template_id = root.get("template_id")
        count = root.get("count")
        if (
            not isinstance(template_id, str)
            or not AGENT_SCHEME_ID_PATTERN.fullmatch(template_id)
        ):
            raise InvalidAgentSchemeError("Корень содержит неверный template_id.")
        if type(count) is not int or count <= 0:
            raise InvalidAgentSchemeError(
                "Количество корневых экземпляров должно быть целым числом больше нуля."
            )
        if template_id in root_template_ids:
            raise InvalidAgentSchemeError(
                "Корневой шаблон не должен повторяться в одной AgentScheme."
            )
        root_template_ids.add(template_id)
        normalized_roots.append({"count": count, "template_id": template_id})

    normalized["roots"] = normalized_roots
    return normalized


def _validate_catalog(
    agent_schemes: list[dict[str, object]],
) -> list[dict[str, object]]:
    normalized_schemes = []
    agent_scheme_ids: set[str] = set()
    for agent_scheme in agent_schemes:
        normalized = _validate_agent_scheme(agent_scheme)
        agent_scheme_id = str(normalized["agent_scheme_id"])
        if agent_scheme_id in agent_scheme_ids:
            raise InvalidAgentSchemeError(
                f"agent_scheme_id '{agent_scheme_id}' встречается несколько раз."
            )
        agent_scheme_ids.add(agent_scheme_id)
        normalized_schemes.append(normalized)
    return normalized_schemes


def _write_agent_schemes(
    project_path: Path,
    agent_schemes: list[dict[str, object]],
) -> Path:
    agent_scheme_file = project_path / AGENT_SCHEMES_FILE_NAME
    temporary_file = agent_scheme_file.with_name(agent_scheme_file.name + ".tmp")
    try:
        temporary_file.write_text(
            json.dumps(
                {"agent_schemes": agent_schemes},
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary_file.replace(agent_scheme_file)
    except (OSError, UnicodeError, TypeError, ValueError) as error:
        try:
            temporary_file.unlink(missing_ok=True)
        except OSError:
            pass
        raise InvalidAgentSchemeError(
            "Не удалось записать файл agent_schemes.json."
        ) from error
    return agent_scheme_file


def load_agent_schemes(project_path: Path) -> list[dict[str, object]]:
    agent_scheme_file = project_path / AGENT_SCHEMES_FILE_NAME
    if not agent_scheme_file.is_file():
        return []

    try:
        document = json.loads(agent_scheme_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise InvalidAgentSchemeError(
            "Файл agent_schemes.json содержит некорректные данные."
        ) from error

    if not isinstance(document, dict) or not isinstance(
        document.get("agent_schemes"),
        list,
    ):
        raise InvalidAgentSchemeError(
            "Файл agent_schemes.json должен содержать массив agent_schemes."
        )
    if any(
        not isinstance(agent_scheme, dict)
        for agent_scheme in document["agent_schemes"]
    ):
        raise InvalidAgentSchemeError(
            "Каждая AgentScheme должна быть JSON-объектом."
        )
    return _validate_catalog(document["agent_schemes"])


def save_agent_scheme(
    project_path: Path,
    agent_scheme: dict[str, object],
) -> Path:
    normalized = _validate_agent_scheme(agent_scheme)
    agent_scheme_id = normalized["agent_scheme_id"]
    agent_schemes = load_agent_schemes(project_path)
    for index, existing_scheme in enumerate(agent_schemes):
        if existing_scheme["agent_scheme_id"] == agent_scheme_id:
            agent_schemes[index] = normalized
            break
    else:
        agent_schemes.append(normalized)
    return _write_agent_schemes(project_path, _validate_catalog(agent_schemes))


def delete_agent_scheme(project_path: Path, agent_scheme_id: str) -> Path:
    from scheme_builder.join_scheme import InvalidJoinSchemeError, load_join_scheme

    agent_schemes = load_agent_schemes(project_path)
    if not any(
        agent_scheme["agent_scheme_id"] == agent_scheme_id
        for agent_scheme in agent_schemes
    ):
        raise InvalidAgentSchemeError(
            f"AgentScheme '{agent_scheme_id}' не найдена."
        )
    try:
        join_scheme = load_join_scheme(project_path)
    except InvalidJoinSchemeError as error:
        raise InvalidAgentSchemeError(str(error)) from error
    if join_scheme is not None and any(
        agent["agent_scheme_id"] == agent_scheme_id
        for agent in join_scheme.get("agents", [])
    ):
        raise InvalidAgentSchemeError(
            "AgentScheme используется в JoinScheme и не может быть удалена."
        )
    remaining_schemes = [
        agent_scheme
        for agent_scheme in agent_schemes
        if agent_scheme["agent_scheme_id"] != agent_scheme_id
    ]
    return _write_agent_schemes(project_path, remaining_schemes)


def build_agent_tree(
    project_path: Path,
    agent_scheme: dict[str, object],
) -> list[dict[str, object]]:
    normalized = _validate_agent_scheme(agent_scheme)
    templates = {
        str(template["template_id"]): template
        for template in load_templates(project_path)
    }
    item_count = 0

    def build_node(
        template_id: str,
        index: int,
        parent_path: str | None,
        join_target: bool = False,
    ) -> dict[str, object]:
        nonlocal item_count
        item_count += 1
        if item_count > MAX_AGENT_ITEMS:
            raise InvalidAgentSchemeError(
                f"AgentScheme содержит больше {MAX_AGENT_ITEMS} узлов."
            )
        segment = f"{template_id}[{index}]"
        full_path = f"{parent_path}/{segment}" if parent_path else segment
        template = templates.get(template_id)
        children: list[dict[str, object]] = []
        if template is not None:
            for include in template.get("includes", []):
                child_template_id = str(include["template_id"])
                for child_index in range(int(include["count"])):
                    children.append(
                        build_node(
                            child_template_id,
                            child_index,
                            full_path,
                            bool(include.get("join_target", False)),
                        )
                    )
        return {
            "children": children,
            "full_path": full_path,
            "index": index,
            "join_target": join_target,
            "missing": template is None,
            "template_id": template_id,
        }

    roots = []
    join_id = 1
    for root in normalized["roots"]:
        template_id = str(root["template_id"])
        for index in range(int(root["count"])):
            node = build_node(template_id, index, None)
            node["join_id"] = str(join_id)
            roots.append(node)
            join_id += 1
    return roots


def build_agent_lists(
    project_path: Path,
    agent_scheme: dict[str, object],
) -> dict[str, list[dict[str, object]]]:
    roots = build_agent_tree(project_path, agent_scheme)
    item_id_list: list[dict[str, object]] = []
    join_id_list: list[dict[str, object]] = []

    def collect(node: dict[str, object]) -> None:
        item_id_list.append({"full_path": node["full_path"], "item_id": None})
        for child in node["children"]:
            collect(child)

    for root in roots:
        collect(root)
        join_id_list.append({
            "full_path": root["full_path"],
            "join_id": root["join_id"],
        })

    return {
        "item_id_list": item_id_list,
        "item_info_list": [],
        "join_id_list": join_id_list,
    }


def build_agent_document(
    project_path: Path,
    agent_scheme: dict[str, object],
    scheme_revision: int = 1,
) -> dict[str, object]:
    normalized = _validate_agent_scheme(agent_scheme)
    if type(scheme_revision) is not int or scheme_revision < 1:
        raise InvalidAgentSchemeError("Ревизия должна быть целым числом больше нуля.")
    templates = {
        template["template_id"]: template for template in load_templates(project_path)
    }
    metrics = {metric["metric_id"]: metric for metric in load_metrics(project_path)}
    used_templates: dict[str, dict[str, object]] = {}
    used_metrics: dict[str, dict[str, object]] = {}
    pending = [root["template_id"] for root in normalized["roots"]]
    while pending:
        template_id = pending.pop(0)
        if template_id in used_templates:
            continue
        if template_id not in templates:
            raise InvalidAgentSchemeError(
                f"Нельзя экспортировать: шаблон '{template_id}' не найден."
            )
        template = templates[template_id]
        used_templates[template_id] = template_for_transport(template)
        for metric_id in template.get("metrics", []):
            if metric_id not in metrics:
                raise InvalidAgentSchemeError(
                    f"Нельзя экспортировать: метрика '{metric_id}' "
                    f"шаблона '{template_id}' не найдена."
                )
            used_metrics[metric_id] = metrics[metric_id]
        pending.extend(include["template_id"] for include in template.get("includes", []))
    return {
        "scheme_revision": scheme_revision,
        "scheme": {
            "metrics": list(used_metrics.values()),
            "templates": list(used_templates.values()),
            **build_agent_lists(project_path, normalized),
        },
    }


def export_agent_scheme(
    project_path: Path,
    agent_scheme: dict[str, object],
    destination: Path,
    scheme_revision: int = 1,
) -> Path:
    document = build_agent_document(project_path, agent_scheme, scheme_revision)
    temporary_file = None
    try:
        protected_files = {
            (project_path / name).resolve()
            for name in (
                "project.json", "metrics.json", "templates.json",
                AGENT_SCHEMES_FILE_NAME, "join_scheme.json",
            )
        }
        if destination.resolve() in protected_files:
            raise InvalidAgentSchemeError("Экспорт не должен заменять файлы комплекса.")
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=".agent-export-", suffix=".tmp", delete=False,
        ) as stream:
            temporary_file = Path(stream.name)
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary_file.replace(destination)
    except (OSError, UnicodeError) as error:
        raise InvalidAgentSchemeError("Не удалось записать файл экспорта AgentScheme.") from error
    finally:
        if temporary_file is not None:
            try:
                temporary_file.unlink(missing_ok=True)
            except OSError:
                pass
    return destination
