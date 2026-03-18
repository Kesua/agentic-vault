from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib import error, parse, request


TODOIST_TASKS_URL = "https://api.todoist.com/api/v1/tasks"
TODOIST_PROJECTS_URL = "https://api.todoist.com/api/v1/projects"
TODOIST_SECTIONS_URL = "https://api.todoist.com/api/v1/sections"

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
TODOIST_TOKEN_PATH = SECRETS_DIR / "todoist_token_personal.json"
DAILY_BRIEFS_ROOT = REPO_ROOT / "10_DailyBriefs"


@dataclass(frozen=True)
class SyncStats:
    fetched_total: int
    due_in_range: int
    families_shown: int
    days_processed: int
    created: int
    updated: int
    unchanged: int


def _load_todoist_token() -> str:
    if not TODOIST_TOKEN_PATH.exists():
        raise RuntimeError(f"Missing token file: {TODOIST_TOKEN_PATH}")

    raw_text = TODOIST_TOKEN_PATH.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise RuntimeError(f"Token file is empty: {TODOIST_TOKEN_PATH}")

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        # Also support plain text token files (non-JSON).
        return raw_text

    if isinstance(payload, dict):
        token = payload.get("token")
        if not isinstance(token, str) or not token.strip():
            raise RuntimeError(f"Token file missing non-empty 'token' field: {TODOIST_TOKEN_PATH}")
        return token.strip()

    if isinstance(payload, str) and payload.strip():
        # Also support raw JSON string format: "todoist_token_here"
        return payload.strip()

    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            token = first.get("token")
            if isinstance(token, str) and token.strip():
                return token.strip()

    raise RuntimeError(
        f"Unsupported token file format in {TODOIST_TOKEN_PATH}. "
        "Use {\"token\":\"...\"}, a raw JSON string token, plain text token, or [{\"token\":\"...\"}]."
    )


def _target_dates(days_ahead: int = 14) -> list[date]:
    if days_ahead < 0:
        raise ValueError("days_ahead must be >= 0")
    today = datetime.now().astimezone().date()
    return [today + timedelta(days=i) for i in range(days_ahead + 1)]


def _fetch_todoist_collection(token: str, url_base: str) -> list[dict[str, Any]]:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    out: list[dict[str, Any]] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()

    while True:
        query: dict[str, str] = {"limit": "200"}
        if cursor:
            query["cursor"] = cursor
        url = url_base + "?" + parse.urlencode(query)

        req = request.Request(url, headers=headers, method="GET")

        try:
            with request.urlopen(req, timeout=30) as resp:
                body = resp.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Todoist API HTTP {exc.code}: {body[:500]}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Todoist API request failed: {exc}") from exc

        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Todoist API returned invalid JSON") from exc

        items: Any = data
        next_cursor: str | None = None
        if isinstance(data, dict):
            # Todoist v1 endpoints commonly wrap collections in "results" (or similar).
            for key in ("results", "items", "tasks", "data"):
                if isinstance(data.get(key), list):
                    items = data[key]
                    break
            for key in ("next_cursor", "next_token", "cursor"):
                value = data.get(key)
                if isinstance(value, str) and value.strip():
                    next_cursor = value.strip()
                    break

        if not isinstance(items, list):
            preview = json.dumps(data, ensure_ascii=False)[:500] if isinstance(data, (dict, list)) else str(data)[:500]
            raise RuntimeError(
                "Unexpected Todoist API response format: expected a list of tasks "
                f"or an object containing one. Response preview: {preview}"
            )

        for item in items:
            if isinstance(item, dict):
                out.append(item)

        if not next_cursor:
            break
        if next_cursor in seen_cursors:
            break
        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return out


def _fetch_active_tasks(token: str) -> list[dict[str, Any]]:
    return _fetch_todoist_collection(token, TODOIST_TASKS_URL)


def _fetch_name_map(token: str, url_base: str) -> dict[str, str]:
    try:
        items = _fetch_todoist_collection(token, url_base)
    except RuntimeError as exc:
        print(f"Warning: metadata lookup failed for {url_base}: {exc}", file=sys.stderr)
        return {}

    out: dict[str, str] = {}
    for item in items:
        item_id = item.get("id")
        name = item.get("name")
        if item_id is None or not isinstance(name, str) or not name.strip():
            continue
        out[str(item_id)] = name.strip()
    return out


def _task_due_date_str(task: dict[str, Any]) -> str | None:
    due = task.get("due")
    if not isinstance(due, dict):
        return None
    due_date = due.get("date")
    if not isinstance(due_date, str) or not due_date.strip():
        return None
    due_date = due_date.strip()
    # Todoist v1 may return a full RFC3339 datetime here for timed tasks.
    if len(due_date) >= 10:
        date_part = due_date[:10]
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_part):
            return date_part
    return due_date


def _sort_key_for_task(task: dict[str, Any]) -> tuple[Any, ...]:
    def _norm_id(value: Any) -> tuple[int, str]:
        if value is None:
            return (1, "")
        return (0, str(value))

    def _norm_int(value: Any) -> tuple[int, int]:
        if isinstance(value, int):
            return (0, value)
        return (1, 0)

    priority = task.get("priority")
    priority_sort = -priority if isinstance(priority, int) else 999

    content = task.get("content")
    content_sort = content.casefold() if isinstance(content, str) else ""

    return (
        *_norm_id(task.get("project_id")),
        *_norm_id(task.get("section_id")),
        *_norm_int(task.get("child_order") if task.get("child_order") is not None else task.get("order")),
        priority_sort,
        content_sort,
    )


def _task_id_str(task: dict[str, Any]) -> str | None:
    task_id = task.get("id")
    if task_id is None:
        return None
    return str(task_id)


def _parent_id_str(task: dict[str, Any]) -> str | None:
    parent_id = task.get("parent_id")
    if parent_id in (None, ""):
        return None
    return str(parent_id)


def _build_task_graph(
    tasks: list[dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    task_by_id: dict[str, dict[str, Any]] = {}
    synthetic_idx = 0
    synthetic_keys: dict[int, str] = {}
    for task in tasks:
        task_id = _task_id_str(task)
        if not task_id:
            synthetic_idx += 1
            task_id = f"__synthetic_{synthetic_idx}"
            synthetic_keys[id(task)] = task_id
        task_by_id[task_id] = task

    def _effective_task_id(task: dict[str, Any]) -> str:
        return _task_id_str(task) or synthetic_keys[id(task)]

    children_by_parent: dict[str, list[dict[str, Any]]] = {}
    roots: list[dict[str, Any]] = []
    for task in task_by_id.values():
        parent_id = _parent_id_str(task)
        if parent_id and parent_id in task_by_id and parent_id != _effective_task_id(task):
            children_by_parent.setdefault(parent_id, []).append(task)
        else:
            roots.append(task)

    for parent_id in children_by_parent:
        children_by_parent[parent_id].sort(key=_sort_key_for_task)
    roots.sort(key=_sort_key_for_task)
    return task_by_id, children_by_parent, roots


def _collect_family_members(
    root: dict[str, Any],
    children_by_parent: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    visited: set[str] = set()

    def _walk(task: dict[str, Any]) -> None:
        task_id = _task_id_str(task) or f"__anon_{id(task)}"
        if task_id in visited:
            return
        visited.add(task_id)
        members.append(task)
        for child in children_by_parent.get(task_id, []):
            _walk(child)

    _walk(root)
    return members


def _group_task_families_by_due_date(
    tasks: list[dict[str, Any]],
    target_days: list[date],
    debug_preview: bool = False,
) -> tuple[
    dict[str, list[str]],
    int,
    dict[str, dict[str, Any]],
    dict[str, list[dict[str, Any]]],
]:
    target_keys = {d.isoformat() for d in target_days}
    grouped: dict[str, list[str]] = {d.isoformat(): [] for d in target_days}
    in_range_count = 0
    debug_rows: list[str] = []
    task_by_id, children_by_parent, roots = _build_task_graph(tasks)

    for task in tasks:
        due_key = _task_due_date_str(task)
        if debug_preview and len(debug_rows) < 10:
            debug_rows.append(
                json.dumps(
                    {
                        "id": task.get("id"),
                        "content": task.get("content"),
                        "due_raw": task.get("due"),
                        "due_key": due_key,
                        "in_target_range": bool(due_key and due_key in target_keys),
                    },
                    ensure_ascii=False,
                )
            )
        if not due_key or due_key not in target_keys:
            continue
        in_range_count += 1

    for root in roots:
        root_id = _task_id_str(root) or f"__anon_{id(root)}"
        member_due_days: set[str] = set()
        for member in _collect_family_members(root, children_by_parent):
            due_key = _task_due_date_str(member)
            if due_key and due_key in target_keys:
                member_due_days.add(due_key)
        for due_key in sorted(member_due_days):
            grouped[due_key].append(root_id)

    for due_key in grouped:
        grouped[due_key].sort(key=lambda root_id: _sort_key_for_task(task_by_id[root_id]))

    if debug_preview:
        print("Debug due preview (first up to 10 tasks):")
        for row in debug_rows:
            print(f"  {row}")

    return grouped, in_range_count, task_by_id, children_by_parent


def _fmt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        if not value:
            return ""
        return ", ".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, separators=(",", ": "))
    return str(value)


def _project_name(task: dict[str, Any], project_names: dict[str, str]) -> str | None:
    project_id = task.get("project_id")
    if project_id is None:
        return None
    project_key = str(project_id)
    return project_names.get(project_key) or project_key


def _section_name(task: dict[str, Any], section_names: dict[str, str]) -> str | None:
    section_id = task.get("section_id")
    if section_id in (None, ""):
        return None
    section_key = str(section_id)
    return section_names.get(section_key) or section_key


def _task_lines(
    task: dict[str, Any],
    *,
    depth: int,
    children_by_parent: dict[str, list[dict[str, Any]]],
    project_names: dict[str, str],
    section_names: dict[str, str],
    visited: set[str],
) -> list[str]:
    lines: list[str] = []
    task_key = _task_id_str(task) or f"__anon_{id(task)}"
    if task_key in visited:
        return lines
    visited.add(task_key)

    bullet_indent = "  " * depth
    field_indent = "  " * (depth + 1)
    content = str(task.get("content") or "(No content)")
    lines.append(f"{bullet_indent}- **{content}**")

    curated_fields: list[tuple[str, Any]] = [
        ("Priority", task.get("priority")),
        ("Labels", task.get("labels")),
        ("Description", task.get("description")),
        ("URL", task.get("url")),
        ("Comment Count", task.get("comment_count")),
    ]

    due = task.get("due")
    if isinstance(due, dict):
        curated_fields.append(("Due", due))

    deadline = task.get("deadline")
    if deadline is not None:
        curated_fields.append(("Deadline", deadline))

    duration = task.get("duration")
    if duration is not None:
        curated_fields.append(("Duration", duration))

    for label, value in curated_fields:
        if value in (None, "", []):
            continue
        lines.append(f"{field_indent}- {label}: {_fmt_value(value)}")

    for child in children_by_parent.get(task_key, []):
        lines.extend(
            _task_lines(
                child,
                depth=depth + 1,
                children_by_parent=children_by_parent,
                project_names=project_names,
                section_names=section_names,
                visited=visited,
            )
        )
    return lines


def _group_roots_by_project_section(
    root_ids: list[str],
    *,
    task_by_id: dict[str, dict[str, Any]],
    project_names: dict[str, str],
    section_names: dict[str, str],
) -> list[tuple[str, list[tuple[str, list[str]]]]]:
    grouped: dict[str, dict[str, list[str]]] = {}

    for root_id in root_ids:
        root = task_by_id.get(root_id)
        if not root:
            continue
        project = _project_name(root, project_names) or "Unknown project"
        section = _section_name(root, section_names) or "No section"
        grouped.setdefault(project, {}).setdefault(section, []).append(root_id)

    def _project_sort_key(name: str) -> str:
        return name.casefold()

    def _section_sort_key(name: str) -> tuple[int, str]:
        if name == "No section":
            return (1, "")
        return (0, name.casefold())

    out: list[tuple[str, list[tuple[str, list[str]]]]] = []
    for project in sorted(grouped, key=_project_sort_key):
        sections = grouped[project]
        section_groups: list[tuple[str, list[str]]] = []
        for section in sorted(sections, key=_section_sort_key):
            section_groups.append((section, sections[section]))
        out.append((project, section_groups))
    return out


def _family_member_count(root_id: str, children_by_parent: dict[str, list[dict[str, Any]]], task_by_id: dict[str, dict[str, Any]]) -> int:
    root = task_by_id.get(root_id)
    if not root:
        return 0
    return len(_collect_family_members(root, children_by_parent))


def _render_tasks_section(
    day_key: str,
    root_ids: list[str],
    *,
    task_by_id: dict[str, dict[str, Any]],
    children_by_parent: dict[str, list[dict[str, Any]]],
    project_names: dict[str, str],
    section_names: dict[str, str],
) -> str:
    now_str = datetime.now().astimezone().isoformat(timespec="seconds")
    total_rendered_tasks = sum(_family_member_count(root_id, children_by_parent, task_by_id) for root_id in root_ids)
    lines: list[str] = [
        "# Tasks",
        "",
        f"- Source: Todoist (active tasks due on {day_key})",
        f"- Synced: {now_str}",
        f"- Families: {len(root_ids)}",
        f"- Count: {total_rendered_tasks}",
        "",
    ]

    if not root_ids:
        lines.append("- No Todoist tasks due.")
        lines.append("")
        return "\n".join(lines)

    grouped = _group_roots_by_project_section(
        root_ids,
        task_by_id=task_by_id,
        project_names=project_names,
        section_names=section_names,
    )

    for p_idx, (project, section_groups) in enumerate(grouped):
        lines.append(f"## {project}")
        lines.append("")
        for s_idx, (section, section_root_ids) in enumerate(section_groups):
            lines.append(f"### {section}")
            lines.append("")
            for r_idx, root_id in enumerate(section_root_ids):
                root = task_by_id.get(root_id)
                if not root:
                    continue
                lines.extend(
                    _task_lines(
                        root,
                        depth=0,
                        children_by_parent=children_by_parent,
                        project_names=project_names,
                        section_names=section_names,
                        visited=set(),
                    )
                )
                if r_idx != len(section_root_ids) - 1:
                    lines.append("")
            if s_idx != len(section_groups) - 1:
                lines.append("")
        if p_idx != len(grouped) - 1:
            lines.append("")

    lines.append("")
    return "\n".join(lines)


def _replace_or_append_tasks_section(existing_text: str, tasks_section: str) -> str:
    section = tasks_section.rstrip() + "\n"
    pattern = re.compile(r"(?ms)^# Tasks\s*$.*?(?=^# |\Z)")
    match = pattern.search(existing_text)
    if match:
        updated = existing_text[: match.start()] + section + existing_text[match.end() :]
    else:
        updated = existing_text
        if updated and not updated.endswith("\n"):
            updated += "\n"
        if updated.strip():
            updated = updated.rstrip("\n") + "\n\n" + section
        else:
            updated = section

    if not updated.endswith("\n"):
        updated += "\n"
    return updated


def _daily_brief_path(day: date) -> Path:
    year = day.strftime("%Y")
    month = day.strftime("%m")
    filename = f"{day.isoformat()}_Daily_Brief.md"
    return DAILY_BRIEFS_ROOT / year / month / filename


def sync_daily_briefs(days_ahead: int = 14, dry_run: bool = False, debug_due_preview: bool = False) -> SyncStats:
    token = _load_todoist_token()
    target_days = _target_dates(days_ahead=days_ahead)
    all_tasks = _fetch_active_tasks(token)
    project_names = _fetch_name_map(token, TODOIST_PROJECTS_URL)
    section_names = _fetch_name_map(token, TODOIST_SECTIONS_URL)
    grouped, due_in_range, task_by_id, children_by_parent = _group_task_families_by_due_date(
        all_tasks,
        target_days,
        debug_preview=debug_due_preview,
    )

    created = 0
    updated = 0
    unchanged = 0
    families_shown = 0

    for day in target_days:
        day_key = day.isoformat()
        root_ids = grouped.get(day_key, [])
        families_shown += len(root_ids)
        path = _daily_brief_path(day)
        tasks_section = _render_tasks_section(
            day_key,
            root_ids,
            task_by_id=task_by_id,
            children_by_parent=children_by_parent,
            project_names=project_names,
            section_names=section_names,
        )

        if path.exists():
            existing = path.read_text(encoding="utf-8")
            new_content = _replace_or_append_tasks_section(existing, tasks_section)
            if new_content == existing:
                unchanged += 1
            else:
                updated += 1
                if not dry_run:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(new_content, encoding="utf-8")
        else:
            created += 1
            if not dry_run:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(tasks_section, encoding="utf-8")

    stats = SyncStats(
        fetched_total=len(all_tasks),
        due_in_range=due_in_range,
        families_shown=families_shown,
        days_processed=len(target_days),
        created=created,
        updated=updated,
        unchanged=unchanged,
    )

    print(f"Fetched active tasks: {stats.fetched_total}")
    print(f"Due tasks in range: {stats.due_in_range}")
    print(f"Families shown across days: {stats.families_shown}")
    print(f"Days processed: {stats.days_processed} (today + {days_ahead} days)")
    print(f"Created files: {stats.created}")
    print(f"Updated files: {stats.updated}")
    print(f"Unchanged files: {stats.unchanged}")
    if dry_run:
        print("Dry run: no files written")
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="daily_brief_todoist")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Sync Todoist tasks into daily briefs (today + 14 days)")
    p_sync.add_argument("--dry-run", action="store_true")
    p_sync.add_argument("--days-ahead", type=int, default=14)
    p_sync.add_argument("--debug-due-preview", action="store_true", help="Print due-date parsing preview for first few tasks")

    args = parser.parse_args(argv)

    if args.cmd == "sync":
        sync_daily_briefs(
            days_ahead=int(args.days_ahead),
            dry_run=bool(args.dry_run),
            debug_due_preview=bool(args.debug_due_preview),
        )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
