"""Единственный редактируемый черновик JoinScheme комплекса."""

import json
from collections import Counter
from copy import deepcopy
from pathlib import Path
from tempfile import NamedTemporaryFile

from scheme_builder.agent_scheme import (
    AGENT_SCHEME_ID_PATTERN, InvalidAgentSchemeError, build_agent_tree, load_agent_schemes,
)
from scheme_builder.template import (
    TEMPLATE_ID_PATTERN, load_templates, template_for_transport,
)

JOIN_SCHEME_FILE_NAME = "join_scheme.json"
AUTO_ASSIGN_SEARCH_LIMIT = 100_000


class InvalidJoinSchemeError(ValueError):
    pass


def _validate_join_scheme(join_scheme: dict[str, object]) -> dict[str, object]:
    if (not isinstance(join_scheme, dict)
            or "root_template_id" not in join_scheme
            or set(join_scheme) - {"root_template_id", "agents"}):
        raise InvalidJoinSchemeError(
            "JoinScheme должна содержать root_template_id и необязательный список agents."
        )
    template_id = join_scheme["root_template_id"]
    if not isinstance(template_id, str) or not TEMPLATE_ID_PATTERN.fullmatch(template_id):
        raise InvalidJoinSchemeError(
            "root_template_id должен содержать только латинские буквы, цифры, '_' и '.'."
        )
    agents = join_scheme.get("agents", [])
    if not isinstance(agents, list):
        raise InvalidJoinSchemeError("agents должен быть списком.")
    for agent in agents:
        if not isinstance(agent, dict) or set(agent) != {"agent_reg_id", "agent_scheme_id", "joins"}:
            raise InvalidJoinSchemeError("Агент должен содержать agent_reg_id, agent_scheme_id, joins.")
        reg_id = agent["agent_reg_id"]
        if not isinstance(reg_id, str):
            raise InvalidJoinSchemeError("agent_reg_id должен быть строкой.")
        scheme_id = agent["agent_scheme_id"]
        if (
            not isinstance(scheme_id, str)
            or (scheme_id and not AGENT_SCHEME_ID_PATTERN.fullmatch(scheme_id))
        ):
            raise InvalidJoinSchemeError("Выберите корректный agent_scheme_id.")
        if not isinstance(agent["joins"], list):
            raise InvalidJoinSchemeError("joins должен быть списком.")
        join_ids = set()
        for join in agent["joins"]:
            if (not isinstance(join, dict) or set(join) != {
                    "agent_item_join_id", "join_item_full_path", "agent_item_full_path"}
                    or any(not isinstance(value, str) or not value.strip() for value in join.values())):
                raise InvalidJoinSchemeError("Привязка должна содержать три непустые строки: "
                                             "agent_item_join_id, join_item_full_path, agent_item_full_path.")
            if join["agent_item_join_id"] in join_ids:
                raise InvalidJoinSchemeError("join_id не должен повторяться у одного агента.")
            join_ids.add(join["agent_item_join_id"])
    # Reference validity is deliberately not a storage constraint: retain stale drafts.
    return deepcopy(join_scheme)


def load_join_scheme(project_path: Path) -> dict[str, object] | None:
    """Прочитать черновик; отсутствие файла означает отсутствие схемы."""
    try:
        text = (project_path / JOIN_SCHEME_FILE_NAME).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeError) as error:
        raise InvalidJoinSchemeError("Не удалось прочитать файл join_scheme.json.") from error
    try:
        document = json.loads(text)
    except json.JSONDecodeError as error:
        raise InvalidJoinSchemeError(
            "Файл join_scheme.json содержит некорректный JSON."
        ) from error
    return _validate_join_scheme(document)


def save_join_scheme(project_path: Path, join_scheme: dict[str, object]) -> Path:
    """Атомарно заменить черновик, не требуя наличия корневого шаблона."""
    normalized = _validate_join_scheme(join_scheme)
    destination = project_path / JOIN_SCHEME_FILE_NAME
    temporary_file = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=project_path,
            prefix=".join-scheme-", suffix=".tmp", delete=False,
        ) as stream:
            temporary_file = Path(stream.name)
            json.dump(normalized, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary_file.replace(destination)
    except (OSError, UnicodeError, TypeError, ValueError) as error:
        raise InvalidJoinSchemeError("Не удалось записать файл join_scheme.json.") from error
    finally:
        if temporary_file is not None:
            try:
                temporary_file.unlink(missing_ok=True)
            except OSError:
                pass
    return destination


def _agent_root_template_ids(
    project_path: Path,
    join_scheme: dict[str, object],
) -> set[str]:
    selected_ids = {
        str(agent["agent_scheme_id"])
        for agent in join_scheme.get("agents", [])
    }
    return {
        str(root["template_id"])
        for definition in load_agent_schemes(project_path)
        if definition["agent_scheme_id"] in selected_ids
        for root in definition["roots"]
    }


def build_join_tree(project_path: Path, join_scheme: dict[str, object]) -> dict[str, object]:
    """Развернуть один корень существующим движком, без индекса в пути корня."""
    normalized = _validate_join_scheme(join_scheme)
    template_id = normalized["root_template_id"]
    agent_scheme = {
        "agent_scheme_id": "join_scheme",
        "name": "JoinScheme",
        "roots": [{"template_id": template_id, "count": 1}],
    }
    try:
        root = build_agent_tree(project_path, agent_scheme)[0]
    except InvalidAgentSchemeError as error:
        raise InvalidJoinSchemeError(str(error)) from error

    agent_root_template_ids = _agent_root_template_ids(project_path, normalized)
    all_nodes = [root]
    for node in all_nodes:
        all_nodes.extend(node["children"])
    has_marked_targets = any(node["join_target"] for node in all_nodes)
    root_prefix = f"{template_id}[0]"
    pending = [root]
    while pending:
        node = pending.pop()
        full_path = str(node["full_path"])
        if full_path == root_prefix or full_path.startswith(root_prefix + "/"):
            node["full_path"] = template_id + full_path[len(root_prefix):]
        node.pop("join_id", None)
        if node is not root and (
            node["join_target"]
            or (
                not has_marked_targets
                and node["template_id"] in agent_root_template_ids
            )
        ):
            node["children"] = []
        pending.extend(node["children"])
    return root


def _manual_join_messages(
    project_path: Path,
    join_scheme: dict[str, object],
) -> list[str]:
    markers = (
        "путь назначения не найден",
        "не является точкой подключения",
        "неверный шаблон назначения",
        "повторное назначение пути",
        "изменился корень",
        "корень не найден",
        "шаблон корня",
        "один join_id назначен несколько раз",
    )
    return [
        "Ручное подключение сохранено: " + issue
        for issue in join_scheme_binding_issues(project_path, join_scheme)
        if any(marker in issue for marker in markers)
    ]


def auto_assign_join_scheme(
    project_path: Path,
    join_scheme: dict[str, object],
) -> tuple[dict[str, object], list[str]]:
    """Дополнить черновик однозначными агентами и привязками."""
    result = _validate_join_scheme(join_scheme)
    result.setdefault("agents", [])
    definitions = {
        item["agent_scheme_id"]: item
        for item in load_agent_schemes(project_path)
    }

    nodes = [build_join_tree(project_path, result)]
    for node in nodes:
        nodes.extend(node["children"])
    targets = [node for node in nodes if node["join_target"] and not node["missing"]]
    if not targets:
        messages = ["В шаблонах комплекса нет точек подключения join_target."]
        messages.extend(_manual_join_messages(project_path, result))
        return result, messages

    target_counts = Counter(str(node["template_id"]) for node in targets)
    remaining_counts = target_counts.copy()
    for agent in result["agents"]:
        definition = definitions.get(agent["agent_scheme_id"])
        if definition is None:
            continue
        for root in build_agent_tree(project_path, definition):
            remaining_counts[str(root["template_id"])] -= 1

    messages: list[str] = []
    if any(count < 0 for count in remaining_counts.values()):
        messages.append("Созданные агенты требуют больше точек, чем есть в JoinScheme.")
    else:
        candidates = []
        for definition in definitions.values():
            roots = build_agent_tree(project_path, definition)
            requirements = Counter(str(root["template_id"]) for root in roots)
            if requirements and set(requirements) <= set(target_counts):
                candidates.append((definition, requirements))

        template_ids = sorted(target_counts, key=str.casefold)
        goal = tuple(remaining_counts[template_id] for template_id in template_ids)
        states: dict[tuple[int, ...], list[list[int]]] = {
            tuple(0 for _ in template_ids): [[]]
        }
        transitions = 0
        search_limited = False
        for _definition, requirements in candidates:
            requirement = tuple(
                requirements[template_id] for template_id in template_ids
            )
            next_states: dict[tuple[int, ...], list[list[int]]] = {}
            for state, partial_solutions in states.items():
                maximum = min(
                    (goal[index] - state[index]) // count
                    for index, count in enumerate(requirement)
                    if count
                )
                for amount in range(maximum + 1):
                    transitions += 1
                    if transitions > AUTO_ASSIGN_SEARCH_LIMIT:
                        search_limited = True
                        break
                    updated = tuple(
                        state[index] + count * amount
                        for index, count in enumerate(requirement)
                    )
                    state_solutions = next_states.setdefault(updated, [])
                    for partial in partial_solutions:
                        if len(state_solutions) >= 2:
                            break
                        state_solutions.append(partial + [amount])
                if search_limited:
                    break
            if search_limited:
                break
            states = next_states

        solutions = [] if search_limited else states.get(goal, [])
        if search_limited:
            messages.append(
                "Слишком много вариантов состава агентов; уточните AgentScheme вручную."
            )
        elif len(solutions) == 1:
            for (definition, _requirements), amount in zip(candidates, solutions[0]):
                for _ in range(amount):
                    result["agents"].append({
                        "agent_reg_id": "",
                        "agent_scheme_id": definition["agent_scheme_id"],
                        "joins": [],
                    })
        elif not solutions:
            messages.append("Набор AgentScheme не покрывает свободные точки подключения.")
        else:
            messages.append("Найдено несколько вариантов состава агентов.")

    occupied = {
        join["join_item_full_path"]
        for agent in result["agents"]
        for join in agent["joins"]
    }
    free_targets = {
        str(node["full_path"]): node
        for node in targets
        if node["full_path"] not in occupied
    }
    pending = []
    for agent in result["agents"]:
        definition = definitions.get(agent["agent_scheme_id"])
        if definition is None:
            continue
        joined_ids = {join["agent_item_join_id"] for join in agent["joins"]}
        for root in build_agent_tree(project_path, definition):
            if root["join_id"] not in joined_ids:
                pending.append((agent, root))

    def assign(source, path: str) -> None:
        agent, root = source
        agent["joins"].append({
            "agent_item_join_id": root["join_id"],
            "agent_item_full_path": root["full_path"],
            "join_item_full_path": path,
        })
        pending.remove(source)
        del free_targets[path]

    changed = True
    while changed:
        changed = False
        for source in list(pending):
            root = source[1]
            choices = [
                path for path, node in free_targets.items()
                if node["template_id"] == root["template_id"]
            ]
            if len(choices) == 1:
                assign(source, choices[0])
                changed = True
                break
        if changed:
            continue
        for path, target in list(free_targets.items()):
            choices = [
                source for source in pending
                if source[1]["template_id"] == target["template_id"]
            ]
            if len(choices) == 1:
                assign(choices[0], path)
                changed = True
                break

    for template_id in sorted(
        {str(source[1]["template_id"]) for source in pending},
        key=str.casefold,
    ):
        sources = [source for source in pending if source[1]["template_id"] == template_id]
        paths = sorted(
            (
                path for path, node in free_targets.items()
                if node["template_id"] == template_id
            ),
            key=str.casefold,
        )
        scheme_ids = {source[0]["agent_scheme_id"] for source in sources}
        if len(scheme_ids) == 1 and len(sources) == len(paths):
            for source, path in zip(list(sources), paths):
                assign(source, path)
        elif sources and paths:
            messages.append(
                f"{template_id}: выберите подключения вручную ({len(paths)} вариантов)."
            )

    messages.extend(_manual_join_messages(project_path, result))

    return result, messages


def join_scheme_binding_issues(project_path: Path, scheme: dict[str, object]) -> list[str]:
    """Diagnose draft references without repairing or mutating the saved mappings."""
    scheme = _validate_join_scheme(scheme)
    issues = []
    destinations = {}
    pending = [build_join_tree(project_path, scheme)]
    while pending:
        node = pending.pop()
        destinations[node["full_path"]] = node
        if node["missing"]:
            issues.append(f"Шаблон не найден: {node['full_path']}.")
        pending.extend(node["children"])
    definitions = {item["agent_scheme_id"]: item for item in load_agent_schemes(project_path)}
    used = {}
    marked_targets = {
        path for path, node in destinations.items() if node["join_target"]
    }
    reg_ids: dict[str, str] = {}
    for agent_index, agent in enumerate(scheme.get("agents", []), start=1):
        reg_id = agent["agent_reg_id"].strip()
        label = reg_id or f"Агент #{agent_index}"
        if not reg_id:
            issues.append(f"{label}: введите agent_reg_id.")
        elif reg_id in reg_ids:
            issues.append(
                f"{label}: agent_reg_id повторяется (уже {reg_ids[reg_id]})."
            )
        else:
            reg_ids[reg_id] = label
        definition = definitions.get(agent["agent_scheme_id"])
        roots = {}
        if not agent["agent_scheme_id"]:
            issues.append(f"{label}: выберите AgentScheme.")
        elif definition is None:
            issues.append(f"{label}: AgentScheme '{agent['agent_scheme_id']}' не найдена.")
        else:
            roots = {node["join_id"]: node for node in build_agent_tree(project_path, definition)}
        joins = {join["agent_item_join_id"]: join for join in agent["joins"]}
        for join_id, root in roots.items():
            if join_id not in joins:
                issues.append(f"{label}: отсутствует привязка join_id={join_id} ({root['full_path']}).")
            if root["missing"]:
                issues.append(f"{label}: шаблон корня {root['full_path']} не найден.")
        for join_id, join in joins.items():
            prefix = f"{label}, join_id={join_id}"
            root = roots.get(join_id)
            if definition is not None:
                if root is None:
                    issues.append(f"{prefix}: корень не найден (сохранён {join['agent_item_full_path']}).")
                elif root["full_path"] != join["agent_item_full_path"]:
                    issues.append(f"{prefix}: изменился корень: {join['agent_item_full_path']} → {root['full_path']}. Подтвердите привязку заново.")
            path = join["join_item_full_path"]
            destination = destinations.get(path)
            if destination is None:
                issues.append(f"{prefix}: путь назначения не найден: {path}.")
            elif marked_targets and not destination["join_target"]:
                issues.append(
                    f"{prefix}: {path} не является точкой подключения."
                )
            elif root is not None and root["template_id"] != destination["template_id"]:
                issues.append(f"{prefix}: неверный шаблон назначения {path}; нужен {root['template_id']}.")
            if path in used:
                issues.append(f"{prefix}: повторное назначение пути {path} (уже {used[path]}).")
            else:
                used[path] = prefix
    for path in sorted(marked_targets - set(used), key=str.casefold):
        issues.append(f"Точка подключения не занята: {path}.")
    return issues


def build_join_document(
    project_path: Path,
    join_scheme: dict[str, object],
    scheme_revision: int = 1,
) -> dict[str, object]:
    """Собрать транспортную JoinScheme для pc_at из редактируемого черновика."""
    normalized = _validate_join_scheme(join_scheme)
    if type(scheme_revision) is not int or scheme_revision < 1:
        raise InvalidJoinSchemeError("Ревизия должна быть целым числом больше нуля.")
    issues = join_scheme_binding_issues(project_path, normalized)
    if issues:
        raise InvalidJoinSchemeError(
            "Нельзя экспортировать JoinScheme:\n" + "\n".join(issues)
        )

    templates = {
        template["template_id"]: template
        for template in load_templates(project_path)
    }
    agent_root_template_ids = _agent_root_template_ids(project_path, normalized)
    root = build_join_tree(project_path, normalized)
    tree_nodes = [root]
    for node in tree_nodes:
        tree_nodes.extend(node["children"])
    has_marked_targets = any(node["join_target"] for node in tree_nodes)
    used_templates: dict[str, dict[str, object]] = {}
    item_id_list: list[dict[str, object]] = []
    pending = [root]
    while pending:
        node = pending.pop(0)
        template_id = str(node["template_id"])
        template = templates.get(template_id)
        if template is None:
            raise InvalidJoinSchemeError(
                f"Нельзя экспортировать: шаблон '{template_id}' не найден."
            )
        if (
            node is root
            or (has_marked_targets and not node["join_target"])
            or (
                not has_marked_targets
                and template_id not in agent_root_template_ids
            )
        ):
            used_templates.setdefault(template_id, template_for_transport(template))
        item_id_list.append({"full_path": node["full_path"], "item_id": None})
        pending[0:0] = node["children"]

    join_list = [
        {
            "joins": [
                {
                    "agent_item_join_id": join["agent_item_join_id"],
                    "join_item_full_path": join["join_item_full_path"],
                }
                for join in agent["joins"]
            ],
            "join_type": "jtAssign",
            "agent_reg_id": agent["agent_reg_id"],
        }
        for agent in normalized.get("agents", [])
    ]
    return {
        "scheme_revision": scheme_revision,
        "scheme": {
            "templates": list(used_templates.values()),
            "item_id_list": item_id_list,
            "join_list": join_list,
            "item_info_list": [],
        },
    }


def export_join_scheme(
    project_path: Path,
    join_scheme: dict[str, object],
    destination: Path,
    scheme_revision: int = 1,
) -> Path:
    document = build_join_document(project_path, join_scheme, scheme_revision)
    protected_files = {
        (project_path / name).resolve()
        for name in (
            "project.json", "metrics.json", "templates.json",
            "agent_schemes.json", JOIN_SCHEME_FILE_NAME,
        )
    }
    if destination.resolve() in protected_files:
        raise InvalidJoinSchemeError("Экспорт не должен заменять файлы комплекса.")

    temporary_file = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=".join-export-", suffix=".tmp", delete=False,
        ) as stream:
            temporary_file = Path(stream.name)
            json.dump(document, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary_file.replace(destination)
    except (OSError, UnicodeError) as error:
        raise InvalidJoinSchemeError(
            "Не удалось записать файл экспорта JoinScheme."
        ) from error
    finally:
        if temporary_file is not None:
            try:
                temporary_file.unlink(missing_ok=True)
            except OSError:
                pass
    return destination
