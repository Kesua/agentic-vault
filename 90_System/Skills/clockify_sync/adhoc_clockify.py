from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import error, parse, request


REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
CLOCKIFY_TOKEN_PATH = SECRETS_DIR / "clockify_token.txt"
API_BASE = "https://api.clockify.me/api/v1"
REPORTS_BASE = "https://reports.api.clockify.me/v1"
CURRENT_TOKEN_OWNER_ID = "6777eb65c22bea50e6e1c8f9"


def _load_clockify_token() -> str:
    if not CLOCKIFY_TOKEN_PATH.exists():
        raise RuntimeError(f"Missing token file: {CLOCKIFY_TOKEN_PATH}")
    token = CLOCKIFY_TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError(f"Clockify token file is empty: {CLOCKIFY_TOKEN_PATH}")
    return token


def _clockify_request(
    method: str,
    url: str,
    *,
    token: str,
    payload: dict[str, Any] | None = None,
) -> Any:
    headers = {
        "X-Api-Key": token,
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
        raise RuntimeError(f"Clockify API HTTP {exc.code}: {body_text[:800]}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Clockify API request failed: {exc}") from exc

    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RuntimeError("Clockify API returned invalid JSON") from exc


def _get_current_user(token: str) -> dict[str, Any]:
    user = _clockify_request("GET", f"{API_BASE}/user", token=token)
    if not isinstance(user, dict):
        raise RuntimeError("Clockify /user response has unexpected shape")
    return user


def _active_workspace_id(user: dict[str, Any]) -> str:
    workspace_id = user.get("activeWorkspace")
    if not isinstance(workspace_id, str) or not workspace_id:
        raise RuntimeError("Clockify user has no active workspace")
    return workspace_id


def _parse_datetime(value: str) -> datetime:
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def _to_clockify_iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _fetch_projects(token: str, workspace_id: str) -> list[dict[str, Any]]:
    url = f"{API_BASE}/workspaces/{workspace_id}/projects?page-size=500"
    data = _clockify_request("GET", url, token=token)
    if not isinstance(data, list):
        raise RuntimeError("Clockify projects response has unexpected shape")
    return data


def _fetch_project_tasks(
    token: str, workspace_id: str, project_id: str
) -> list[dict[str, Any]]:
    data = _clockify_request(
        "GET",
        f"{API_BASE}/workspaces/{workspace_id}/projects/{project_id}/tasks?page-size=500",
        token=token,
    )
    if not isinstance(data, list):
        raise RuntimeError("Clockify tasks response has unexpected shape")
    return data


def _normalize_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(project.get("id") or ""),
        "name": str(project.get("name") or ""),
        "clientName": str(project.get("clientName") or ""),
        "billable": bool(project.get("billable")),
        "archived": bool(project.get("archived")),
        "color": str(project.get("color") or ""),
    }


def _match_single(
    items: list[dict[str, Any]], *, key: str, query: str, label: str
) -> dict[str, Any]:
    q = query.casefold().strip()
    if not q:
        raise RuntimeError(f"Missing {label} selector")

    exact: list[dict[str, Any]] = []
    contains: list[dict[str, Any]] = []
    for item in items:
        value = str(item.get(key) or "")
        if not value:
            continue
        if value.casefold() == q:
            exact.append(item)
        elif q in value.casefold():
            contains.append(item)

    matches = exact or contains
    if not matches:
        raise RuntimeError(f"No {label} matched '{query}'")
    if len(matches) > 1:
        rendered = ", ".join(str(item.get(key) or "") for item in matches[:8])
        raise RuntimeError(f"Ambiguous {label} '{query}'. Matches: {rendered}")
    return matches[0]


def _resolve_project(
    token: str,
    workspace_id: str,
    *,
    project_id: str | None,
    project_name: str | None,
) -> dict[str, Any]:
    projects = _fetch_projects(token, workspace_id)
    active_projects = [
        project for project in projects if not bool(project.get("archived"))
    ]
    if project_id:
        for project in active_projects:
            if str(project.get("id") or "") == project_id:
                return project
        raise RuntimeError(f"No active project found for id '{project_id}'")
    if project_name:
        searchable = []
        for project in active_projects:
            cloned = dict(project)
            cloned["_search_name"] = " / ".join(
                part
                for part in [
                    str(project.get("clientName") or "").strip(),
                    str(project.get("name") or "").strip(),
                ]
                if part
            )
            searchable.append(cloned)
        matched = _match_single(
            searchable, key="_search_name", query=project_name, label="project"
        )
        matched.pop("_search_name", None)
        return matched
    raise RuntimeError("Specify --project-id or --project")


def _resolve_task(
    token: str,
    workspace_id: str,
    project_id: str,
    *,
    task_id: str | None,
    task_name: str | None,
) -> dict[str, Any] | None:
    if task_id is None and task_name is None:
        return None
    tasks = [
        task
        for task in _fetch_project_tasks(token, workspace_id, project_id)
        if not bool(task.get("archived"))
    ]
    if task_id:
        for task in tasks:
            if str(task.get("id") or "") == task_id:
                return task
        raise RuntimeError(f"No active task found for id '{task_id}'")
    return _match_single(tasks, key="name", query=str(task_name), label="task")


def _fetch_time_entries(
    token: str,
    workspace_id: str,
    user_id: str,
    *,
    start: datetime,
    end: datetime,
    hydrated: bool = True,
) -> list[dict[str, Any]]:
    params = {
        "start": _to_clockify_iso(start),
        "end": _to_clockify_iso(end),
        "hydrated": str(hydrated).lower(),
        "page-size": "500",
    }
    url = f"{API_BASE}/workspaces/{workspace_id}/user/{user_id}/time-entries?{parse.urlencode(params)}"
    data = _clockify_request("GET", url, token=token)
    if not isinstance(data, list):
        raise RuntimeError("Clockify time entries response has unexpected shape")
    return data


def _normalize_time_entry(entry: dict[str, Any]) -> dict[str, Any]:
    project = entry.get("project") if isinstance(entry.get("project"), dict) else {}
    task = entry.get("task") if isinstance(entry.get("task"), dict) else {}
    time_interval = (
        entry.get("timeInterval") if isinstance(entry.get("timeInterval"), dict) else {}
    )
    duration = str(time_interval.get("duration") or "")
    return {
        "id": str(entry.get("id") or ""),
        "description": str(entry.get("description") or ""),
        "project": {
            "id": str(project.get("id") or entry.get("projectId") or ""),
            "name": str(project.get("name") or ""),
            "clientName": str(project.get("clientName") or ""),
        },
        "task": {
            "id": str(task.get("id") or entry.get("taskId") or ""),
            "name": str(task.get("name") or ""),
        },
        "billable": bool(entry.get("billable")),
        "tagIds": entry.get("tagIds") or [],
        "timeInterval": {
            "start": time_interval.get("start"),
            "end": time_interval.get("end"),
            "duration": duration,
        },
    }


def _matches_entry(
    entry: dict[str, Any],
    *,
    query: str | None,
    project_query: str | None,
    task_query: str | None,
) -> bool:
    if query:
        q = query.casefold()
        desc = str(entry.get("description") or "")
        project = entry.get("project") if isinstance(entry.get("project"), dict) else {}
        task = entry.get("task") if isinstance(entry.get("task"), dict) else {}
        haystacks = [
            desc,
            str(project.get("name") or ""),
            str(project.get("clientName") or ""),
            str(task.get("name") or ""),
        ]
        if not any(q in item.casefold() for item in haystacks if item):
            return False

    if project_query:
        project = entry.get("project") if isinstance(entry.get("project"), dict) else {}
        rendered = " / ".join(
            part
            for part in [
                str(project.get("clientName") or "").strip(),
                str(project.get("name") or "").strip(),
            ]
            if part
        )
        if project_query.casefold() not in rendered.casefold():
            return False

    if task_query:
        task = entry.get("task") if isinstance(entry.get("task"), dict) else {}
        if task_query.casefold() not in str(task.get("name") or "").casefold():
            return False

    return True


def _summary_payload(user_id: str, start: datetime, end: datetime) -> dict[str, Any]:
    return {
        "dateRangeStart": _to_clockify_iso(start),
        "dateRangeEnd": _to_clockify_iso(end),
        "summaryFilter": {"groups": ["PROJECT"]},
        "users": {"contains": "CONTAINS", "ids": [user_id], "status": "ACTIVE"},
        "amountShown": "HIDE_AMOUNT",
    }


def command_whoami(_: argparse.Namespace) -> None:
    token = _load_clockify_token()
    user = _get_current_user(token)
    out = {
        "id": str(user.get("id") or ""),
        "email": str(user.get("email") or ""),
        "name": str(user.get("name") or ""),
        "activeWorkspace": _active_workspace_id(user),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def command_projects(args: argparse.Namespace) -> None:
    token = _load_clockify_token()
    user = _get_current_user(token)
    projects = _fetch_projects(token, _active_workspace_id(user))

    filtered: list[dict[str, Any]] = []
    for project in projects:
        if not args.include_archived and bool(project.get("archived")):
            continue
        rendered = " / ".join(
            part
            for part in [
                str(project.get("clientName") or "").strip(),
                str(project.get("name") or "").strip(),
            ]
            if part
        )
        if args.query and args.query.casefold() not in rendered.casefold():
            continue
        filtered.append(_normalize_project(project))

    filtered.sort(
        key=lambda item: (item["clientName"].casefold(), item["name"].casefold())
    )
    print(
        json.dumps(
            {"count": len(filtered), "projects": filtered[: args.limit]},
            ensure_ascii=False,
            indent=2,
        )
    )


def command_tasks(args: argparse.Namespace) -> None:
    token = _load_clockify_token()
    user = _get_current_user(token)
    workspace_id = _active_workspace_id(user)
    project = _resolve_project(
        token, workspace_id, project_id=args.project_id, project_name=args.project
    )
    tasks = [
        task
        for task in _fetch_project_tasks(
            token, workspace_id, str(project.get("id") or "")
        )
        if not bool(task.get("archived"))
    ]
    if args.query:
        tasks = [
            task
            for task in tasks
            if args.query.casefold() in str(task.get("name") or "").casefold()
        ]
    out = {
        "project": _normalize_project(project),
        "count": len(tasks),
        "tasks": [
            {
                "id": str(task.get("id") or ""),
                "name": str(task.get("name") or ""),
                "billable": bool(task.get("billable")),
            }
            for task in tasks[: args.limit]
        ],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def command_list(args: argparse.Namespace) -> None:
    token = _load_clockify_token()
    user = _get_current_user(token)
    workspace_id = _active_workspace_id(user)
    user_id = str(user.get("id") or "")
    start = _parse_datetime(args.start)
    end = _parse_datetime(args.end)
    if end <= start:
        raise RuntimeError("--end must be after --start")

    entries = _fetch_time_entries(token, workspace_id, user_id, start=start, end=end)
    normalized = [_normalize_time_entry(entry) for entry in entries]
    filtered = [
        entry
        for entry in normalized
        if _matches_entry(
            entry, query=args.query, project_query=args.project, task_query=args.task
        )
    ]
    filtered.sort(key=lambda item: str(item["timeInterval"]["start"] or ""))
    print(
        json.dumps(
            {"count": len(filtered), "entries": filtered[: args.limit]},
            ensure_ascii=False,
            indent=2,
        )
    )


def command_summary(args: argparse.Namespace) -> None:
    token = _load_clockify_token()
    user = _get_current_user(token)
    workspace_id = _active_workspace_id(user)
    user_id = str(user.get("id") or "")
    start = _parse_datetime(args.start)
    end = _parse_datetime(args.end)
    if end <= start:
        raise RuntimeError("--end must be after --start")

    payload = _summary_payload(user_id, start, end)
    data = _clockify_request(
        "POST",
        f"{REPORTS_BASE}/workspaces/{workspace_id}/reports/summary",
        token=token,
        payload=payload,
    )

    totals = data.get("totals") if isinstance(data, dict) else None
    group_one = data.get("groupOne") if isinstance(data, dict) else None
    if not isinstance(totals, list) or not isinstance(group_one, list):
        raise RuntimeError("Clockify summary response has unexpected shape")

    rows: list[dict[str, Any]] = []
    for item in group_one:
        if not isinstance(item, dict):
            continue
        rendered = " / ".join(
            part
            for part in [
                str(item.get("clientName") or "").strip(),
                str(item.get("name") or "").strip(),
            ]
            if part
        )
        if args.project and args.project.casefold() not in rendered.casefold():
            continue
        rows.append(
            {
                "projectId": str(item.get("_id") or ""),
                "clientName": str(item.get("clientName") or ""),
                "projectName": str(item.get("name") or ""),
                "durationSeconds": int(item.get("duration") or 0),
                "durationHours": round(int(item.get("duration") or 0) / 3600, 2),
            }
        )

    total_seconds = 0
    if totals and isinstance(totals[0], dict):
        total_seconds = int(totals[0].get("totalTime") or 0)

    if args.project:
        total_seconds = sum(row["durationSeconds"] for row in rows)

    out = {
        "user": {
            "id": user_id,
            "email": str(user.get("email") or ""),
            "name": str(user.get("name") or ""),
        },
        "start": _to_clockify_iso(start),
        "end": _to_clockify_iso(end),
        "totalSeconds": total_seconds,
        "totalHours": round(total_seconds / 3600, 2),
        "groups": rows,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


def command_create_entry(args: argparse.Namespace) -> None:
    token = _load_clockify_token()
    user = _get_current_user(token)
    workspace_id = _active_workspace_id(user)
    user_id = str(user.get("id") or "")

    project = _resolve_project(
        token, workspace_id, project_id=args.project_id, project_name=args.project
    )
    task = _resolve_task(
        token,
        workspace_id,
        str(project.get("id") or ""),
        task_id=args.task_id,
        task_name=args.task,
    )

    start = _parse_datetime(args.start)
    if args.end:
        end = _parse_datetime(args.end)
    else:
        end = start + timedelta(minutes=args.duration_minutes)
    if end <= start:
        raise RuntimeError("Entry end must be after entry start")

    payload: dict[str, Any] = {
        "start": _to_clockify_iso(start),
        "end": _to_clockify_iso(end),
        "billable": args.billable,
        "description": args.description or "",
        "projectId": str(project.get("id") or ""),
    }
    if task is not None:
        payload["taskId"] = str(task.get("id") or "")

    created = _clockify_request(
        "POST",
        f"{API_BASE}/workspaces/{workspace_id}/user/{user_id}/time-entries",
        token=token,
        payload=payload,
    )
    print(
        json.dumps(_normalize_time_entry(created or {}), ensure_ascii=False, indent=2)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adhoc_clockify",
        description=(
            "Ad-hoc Clockify assistant for the current token owner "
            f"({CURRENT_TOKEN_OWNER_ID}): inspect only that user's entries and explicitly create new entries."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_whoami = sub.add_parser(
        "whoami", help="Show the current Clockify token owner and active workspace"
    )
    p_whoami.set_defaults(func=command_whoami)

    p_projects = sub.add_parser(
        "projects", help="List active projects in the current workspace"
    )
    p_projects.add_argument("--query")
    p_projects.add_argument("--include-archived", action="store_true")
    p_projects.add_argument("--limit", type=int, default=50)
    p_projects.set_defaults(func=command_projects)

    p_tasks = sub.add_parser("tasks", help="List active tasks for one project")
    p_tasks.add_argument("--project-id")
    p_tasks.add_argument("--project")
    p_tasks.add_argument("--query")
    p_tasks.add_argument("--limit", type=int, default=50)
    p_tasks.set_defaults(func=command_tasks)

    p_list = sub.add_parser(
        "list", help="List only the current user's time entries in a date window"
    )
    p_list.add_argument(
        "--start",
        required=True,
        help="ISO datetime, for example 2026-03-01T00:00:00+01:00",
    )
    p_list.add_argument(
        "--end",
        required=True,
        help="ISO datetime, for example 2026-03-08T00:00:00+01:00",
    )
    p_list.add_argument("--query")
    p_list.add_argument("--project")
    p_list.add_argument("--task")
    p_list.add_argument("--limit", type=int, default=100)
    p_list.set_defaults(func=command_list)

    p_summary = sub.add_parser(
        "summary",
        help="Summarize only the current user's time by project in a date window",
    )
    p_summary.add_argument(
        "--start",
        required=True,
        help="ISO datetime, for example 2026-03-01T00:00:00+01:00",
    )
    p_summary.add_argument(
        "--end",
        required=True,
        help="ISO datetime, for example 2026-03-08T00:00:00+01:00",
    )
    p_summary.add_argument("--project")
    p_summary.set_defaults(func=command_summary)

    p_create = sub.add_parser(
        "create-entry", help="Create a new time entry for the current token owner only"
    )
    p_create.add_argument("--project-id")
    p_create.add_argument("--project")
    p_create.add_argument("--task-id")
    p_create.add_argument("--task")
    p_create.add_argument(
        "--start",
        required=True,
        help="ISO datetime, for example 2026-03-11T09:00:00+01:00",
    )
    p_create.add_argument(
        "--end", help="ISO datetime. If omitted, --duration-minutes is used."
    )
    p_create.add_argument("--duration-minutes", type=int, default=60)
    p_create.add_argument("--description")
    p_create.add_argument("--billable", action="store_true")
    p_create.set_defaults(func=command_create_entry)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
