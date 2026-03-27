from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


REPO_ROOT = Path(__file__).resolve().parents[3]
TODOIST_SKILL_DIR = REPO_ROOT / "90_System" / "Skills" / "daily_brief_todoist"
if str(TODOIST_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(TODOIST_SKILL_DIR))

import daily_brief_todoist as todo_base  # type: ignore # noqa: E402


def _todoist_request(
    method: str, url: str, *, token: str, payload: dict[str, Any] | None = None
) -> Any:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    body: bytes | None = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url, headers=headers, data=body, method=method)
    try:
        with request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
    except error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Todoist API HTTP {exc.code}: {body_text[:500]}") from exc  # type: ignore
    except error.URLError as exc:
        raise RuntimeError(f"Todoist API request failed: {exc}") from exc

    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Todoist API returned invalid JSON") from exc


def _fetch_projects(token: str) -> list[dict[str, Any]]:
    return todo_base._fetch_todoist_collection(token, todo_base.TODOIST_PROJECTS_URL)


def _fetch_sections(token: str) -> list[dict[str, Any]]:
    return todo_base._fetch_todoist_collection(token, todo_base.TODOIST_SECTIONS_URL)


def _fetch_tasks(token: str) -> list[dict[str, Any]]:
    return todo_base._fetch_active_tasks(token)


def _resolve_project_id(
    token: str, *, project_id: str | None, project_name: str | None
) -> str | None:
    if project_id:
        return str(project_id)
    if not project_name:
        return None

    projects = _fetch_projects(token)
    exact: list[str] = []
    partial: list[str] = []
    matched_ids: dict[str, str] = {}
    query = project_name.casefold().strip()
    for project in projects:
        raw_id = project.get("id")
        if raw_id is None:
            continue
        name = str(project.get("name") or "").strip()
        if not name:
            continue
        project_id_str = str(raw_id)
        if name.casefold() == query:
            exact.append(name)
            matched_ids[name] = project_id_str
        elif query in name.casefold():
            partial.append(name)
            matched_ids[name] = project_id_str

    if len(exact) == 1:
        return matched_ids[exact[0]]
    if len(exact) > 1:
        rendered = ", ".join(sorted(exact))
        raise RuntimeError(
            f"Ambiguous project '{project_name}'. Exact matches: {rendered}"
        )
    if len(partial) == 1:
        return matched_ids[partial[0]]
    if len(partial) > 1:
        rendered = ", ".join(sorted(partial))
        raise RuntimeError(f"Ambiguous project '{project_name}'. Matches: {rendered}")
    raise RuntimeError(f"Project '{project_name}' not found")


def _resolve_section_id(
    token: str,
    *,
    section_id: str | None,
    section_name: str | None,
    project_id: str | None,
) -> str | None:
    if section_id:
        return str(section_id)
    if not section_name:
        return None

    query = section_name.casefold().strip()
    matches: list[tuple[str, str]] = []
    for section in _fetch_sections(token):
        raw_id = section.get("id")
        if raw_id is None:
            continue
        raw_project_id = section.get("project_id")
        if project_id is not None and str(raw_project_id or "") != str(project_id):
            continue
        name = str(section.get("name") or "").strip()
        if not name:
            continue
        if name.casefold() == query or query in name.casefold():
            matches.append((str(raw_id), name))

    if len(matches) == 1:
        return matches[0][0]
    if len(matches) > 1:
        rendered = ", ".join(sorted(name for _, name in matches))
        raise RuntimeError(f"Ambiguous section '{section_name}'. Matches: {rendered}")
    raise RuntimeError(f"Section '{section_name}' not found")


def _matches_query(task: dict[str, Any], query: str) -> bool:
    q = query.casefold()
    haystacks = [
        str(task.get("content") or ""),
        str(task.get("description") or ""),
        " ".join(str(x) for x in (task.get("labels") or [])),
    ]
    due = task.get("due") or {}
    if isinstance(due, dict):
        haystacks.append(str(due.get("string") or ""))
        haystacks.append(str(due.get("date") or ""))
    return any(q in text.casefold() for text in haystacks if text)


def _resolve_inbox_project_id(token: str) -> str | None:
    projects = _fetch_projects(token)
    fallback: str | None = None
    for project in projects:
        project_id = project.get("id")
        if project_id is None:
            continue
        if (
            isinstance(project.get("is_inbox_project"), bool)
            and project["is_inbox_project"]
        ):
            return str(project_id)
        name = str(project.get("name") or "").strip()
        if name.casefold() == "inbox" and fallback is None:
            fallback = str(project_id)
    return fallback


def _normalize_task(
    task: dict[str, Any], project_names: dict[str, str]
) -> dict[str, Any]:
    due = task.get("due") if isinstance(task.get("due"), dict) else None
    project_id = task.get("project_id")
    url = task.get("url")
    return {
        "id": str(task.get("id") or ""),
        "content": str(task.get("content") or ""),
        "description": str(task.get("description") or ""),
        "priority": task.get("priority"),
        "project": project_names.get(
            str(project_id), str(project_id) if project_id is not None else ""
        ),
        "labels": task.get("labels") or [],
        "due": due,
        "url": url if isinstance(url, str) else None,
    }


def command_list(args: argparse.Namespace) -> None:
    token = todo_base._load_todoist_token()
    tasks = _fetch_tasks(token)
    project_names = todo_base._fetch_name_map(token, todo_base.TODOIST_PROJECTS_URL)

    filtered: list[dict[str, Any]] = []
    for task in tasks:
        if args.query and not _matches_query(task, args.query):
            continue
        if args.priority is not None and task.get("priority") != args.priority:
            continue
        if args.label:
            labels = {str(x).casefold() for x in (task.get("labels") or [])}
            if args.label.casefold() not in labels:
                continue
        if args.project:
            project_name = project_names.get(str(task.get("project_id") or ""), "")
            if args.project.casefold() not in project_name.casefold():
                continue
        due_key = todo_base._task_due_date_str(task)
        if args.due_on and due_key != args.due_on:
            continue
        if args.due_before and (not due_key or due_key >= args.due_before):
            continue
        if args.due_after and (not due_key or due_key <= args.due_after):
            continue
        filtered.append(task)

    filtered.sort(key=todo_base._sort_key_for_task)
    normalized = [
        _normalize_task(task, project_names) for task in filtered[: args.limit]  # type: ignore
    ]
    print(
        json.dumps(
            {"count": len(filtered), "tasks": normalized}, ensure_ascii=False, indent=2
        )
    )


def command_show(args: argparse.Namespace) -> None:
    token = todo_base._load_todoist_token()
    task = _todoist_request(
        "GET", f"{todo_base.TODOIST_TASKS_URL}/{args.task_id}", token=token
    )
    project_names = todo_base._fetch_name_map(token, todo_base.TODOIST_PROJECTS_URL)
    print(
        json.dumps(
            _normalize_task(task or {}, project_names), ensure_ascii=False, indent=2
        )
    )


def _build_create_payload(
    args: argparse.Namespace, *, token: str, default_to_inbox: bool
) -> tuple[dict[str, Any], str | None]:
    if args.due_string and (args.due_date or args.due_datetime):
        raise RuntimeError(
            "Use only one of --due-string, --due-date, or --due-datetime"
        )
    if args.due_date and args.due_datetime:
        raise RuntimeError("Use only one of --due-date or --due-datetime")
    if args.duration_minutes is not None and not args.due_datetime:
        raise RuntimeError("--duration-minutes requires --due-datetime")

    payload: dict[str, Any] = {"content": args.content}
    if args.description:
        payload["description"] = args.description
    if args.priority is not None:
        payload["priority"] = args.priority
    if args.due_string:
        payload["due_string"] = args.due_string
    if args.due_date:
        payload["due_date"] = args.due_date
    if args.due_datetime:
        payload["due_datetime"] = args.due_datetime
    if args.duration_minutes is not None:
        payload["duration"] = args.duration_minutes
        payload["duration_unit"] = "minute"
    if args.labels:
        payload["labels"] = args.labels

    resolved_project_id = _resolve_project_id(
        token, project_id=args.project_id, project_name=args.project
    )
    if resolved_project_id:
        payload["project_id"] = resolved_project_id
    elif default_to_inbox:
        inbox_project_id = _resolve_inbox_project_id(token)
        if inbox_project_id:
            payload["project_id"] = inbox_project_id
            resolved_project_id = inbox_project_id

    resolved_section_id = _resolve_section_id(
        token,
        section_id=args.section_id,
        section_name=args.section,
        project_id=resolved_project_id,
    )
    if resolved_section_id:
        payload["section_id"] = resolved_section_id

    if args.parent_id:
        payload["parent_id"] = args.parent_id
    if args.assignee_id:
        payload["assignee_id"] = args.assignee_id

    return payload, resolved_project_id


def command_create_inbox_task(args: argparse.Namespace) -> None:
    token = todo_base._load_todoist_token()
    payload, resolved_project_id = _build_create_payload(
        args, token=token, default_to_inbox=True
    )

    created = _todoist_request(
        "POST", todo_base.TODOIST_TASKS_URL, token=token, payload=payload
    )
    out = {
        "id": str((created or {}).get("id") or ""),
        "content": (created or {}).get("content") or args.content,
        "project_id": (created or {}).get("project_id") or resolved_project_id,
        "section_id": (created or {}).get("section_id") or payload.get("section_id"),
        "parent_id": (created or {}).get("parent_id") or payload.get("parent_id"),
        "assignee_id": (created or {}).get("assignee_id") or payload.get("assignee_id"),
        "labels": (created or {}).get("labels") or payload.get("labels") or [],
        "due": (created or {}).get("due"),
        "priority": (created or {}).get("priority"),
        "duration": (created or {}).get("duration"),
        "url": (created or {}).get("url"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def command_create_task(args: argparse.Namespace) -> None:
    token = todo_base._load_todoist_token()
    payload, resolved_project_id = _build_create_payload(
        args, token=token, default_to_inbox=False
    )

    created = _todoist_request(
        "POST", todo_base.TODOIST_TASKS_URL, token=token, payload=payload
    )
    out = {
        "id": str((created or {}).get("id") or ""),
        "content": (created or {}).get("content") or args.content,
        "project_id": (created or {}).get("project_id") or resolved_project_id,
        "section_id": (created or {}).get("section_id") or payload.get("section_id"),
        "parent_id": (created or {}).get("parent_id") or payload.get("parent_id"),
        "assignee_id": (created or {}).get("assignee_id") or payload.get("assignee_id"),
        "labels": (created or {}).get("labels") or payload.get("labels") or [],
        "due": (created or {}).get("due"),
        "priority": (created or {}).get("priority"),
        "duration": (created or {}).get("duration"),
        "url": (created or {}).get("url"),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def _add_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--content", required=True)
    parser.add_argument("--description")
    parser.add_argument("--priority", type=int, choices=[1, 2, 3, 4])
    parser.add_argument("--project-id")
    parser.add_argument("--project")
    parser.add_argument("--section-id")
    parser.add_argument("--section")
    parser.add_argument("--parent-id", help="Parent task ID for creating a subtask")
    parser.add_argument(
        "--assignee-id", help="Todoist assignee user ID for shared tasks"
    )
    parser.add_argument(
        "--label", dest="labels", action="append", help="Repeat for multiple labels"
    )
    parser.add_argument("--due-string")
    parser.add_argument("--due-date")
    parser.add_argument(
        "--due-datetime", help="RFC3339 datetime, for example 2026-03-12T10:00:00+01:00"
    )
    parser.add_argument("--duration-minutes", type=int)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adhoc_todoist",
        description="Ad-hoc Todoist assistant: inspect tasks and explicitly create new Todoist tasks.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser(
        "list", help="List active Todoist tasks with optional filters"
    )
    p_list.add_argument("--query")
    p_list.add_argument("--project")
    p_list.add_argument("--label")
    p_list.add_argument("--priority", type=int, choices=[1, 2, 3, 4])
    p_list.add_argument("--due-on", dest="due_on")
    p_list.add_argument("--due-before", dest="due_before")
    p_list.add_argument("--due-after", dest="due_after")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.set_defaults(func=command_list)

    p_show = sub.add_parser("show", help="Show one Todoist task by ID")
    p_show.add_argument("--task-id", required=True)
    p_show.set_defaults(func=command_show)

    p_create = sub.add_parser(
        "create-task",
        help="Create a new task with optional custom project, labels, and due scheduling",
    )
    _add_create_arguments(p_create)
    p_create.set_defaults(func=command_create_task)

    p_create_inbox = sub.add_parser(
        "create-inbox-task", help="Create a new task in Todoist Inbox"
    )
    _add_create_arguments(p_create_inbox)
    p_create_inbox.set_defaults(func=command_create_inbox_task)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
