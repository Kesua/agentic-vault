from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
QUEUE_ROOT = REPO_ROOT / "90_System" / "TaskQueue"
STATE_DIRS = {
    "pending": QUEUE_ROOT / "pending",
    "running": QUEUE_ROOT / "running",
    "done": QUEUE_ROOT / "done",
    "failed": QUEUE_ROOT / "failed",
}
TASK_TEMPLATE_PATH = QUEUE_ROOT / "Templates" / "Task_TEMPLATE.md"


def _configure_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_stdio()


@dataclass
class TaskRecord:
    path: Path
    meta: dict[str, object]
    body: str

    @property
    def title(self) -> str:
        match = re.search(r"(?m)^#\s+(.+?)\s*$", self.body)
        return match.group(1).strip() if match else self.path.stem

    @property
    def task_id(self) -> str:
        return str(self.meta.get("id", self.path.stem))

    @property
    def status(self) -> str:
        return str(self.meta.get("status", "")).strip() or self.path.parent.name

    @property
    def attempt_count(self) -> int:
        raw = self.meta.get("attempt_count", 0)
        try:
            return int(raw)
        except Exception:
            return 0

    @property
    def max_attempts(self) -> int:
        raw = self.meta.get("max_attempts", 3)
        try:
            return int(raw)
        except Exception:
            return 3


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _ensure_dirs() -> None:
    QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
    for path in STATE_DIRS.values():
        path.mkdir(parents=True, exist_ok=True)
    TASK_TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _yaml_scalar(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return '""'
    text = str(value)
    if text == "":
        return '""'
    if re.fullmatch(r"-?\d+", text):
        return text
    return _yaml_quote(text)


def _parse_yaml_value(raw: str) -> object:
    value = raw.strip()
    if not value:
        return ""
    if len(value) >= 2 and value[0] == value[-1] == '"':
        inner = value[1:-1]
        return inner.replace('\\"', '"').replace("\\\\", "\\")
    if value in {"true", "false"}:
        return value == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    match = re.match(r"(?s)^\ufeff?---\r?\n(.*?)\r?\n---\r?\n?(.*)$", text)
    if not match:
        return {}, text
    meta: dict[str, object] = {}
    for raw_line in match.group(1).splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = _parse_yaml_value(value)
    return meta, match.group(2)


def _render_frontmatter(meta: dict[str, object]) -> str:
    ordered_keys = [
        "id",
        "status",
        "created_at",
        "updated_at",
        "source",
        "requested_by",
        "chat_id",
        "priority",
        "blocked_by",
        "worker",
        "claimed_at",
        "completed_at",
        "expires_at",
        "attempt_count",
        "max_attempts",
        "parent_task_id",
    ]
    lines = ["---"]
    emitted: set[str] = set()
    for key in ordered_keys:
        if key in meta:
            lines.append(f"{key}: {_yaml_scalar(meta[key])}")
            emitted.add(key)
    for key in sorted(meta):
        if key in emitted:
            continue
        lines.append(f"{key}: {_yaml_scalar(meta[key])}")
    lines.append("---")
    return "\n".join(lines)


def _render_task(meta: dict[str, object], body: str) -> str:
    normalized_body = body.rstrip() + "\n"
    return _render_frontmatter(meta) + "\n\n" + normalized_body


def _load_task(path: Path) -> TaskRecord:
    text = path.read_text(encoding="utf-8")
    meta, body = _split_frontmatter(text)
    return TaskRecord(path=path, meta=meta, body=body)


def _write_task(path: Path, meta: dict[str, object], body: str) -> None:
    path.write_text(_render_task(meta, body), encoding="utf-8")


def _slug(text: str) -> str:
    compact = re.sub(r"[^A-Za-z0-9]+", "-", text.strip()).strip("-").lower()
    return compact[:60] or "task"


def _task_filename(task_id: str, title: str) -> str:
    return f"{task_id}__{_slug(title)}.md"


def _append_line(body: str, section_heading: str, line: str) -> str:
    section_pattern = rf"(?ms)^##\s+{re.escape(section_heading)}\s*$"
    match = re.search(section_pattern, body)
    dated_line = f"- {_now()} {line}".rstrip()
    if not match:
        extra = f"\n## {section_heading}\n{dated_line}\n"
        return body.rstrip() + extra

    next_section = re.search(r"(?m)^##\s+", body[match.end() :])
    if next_section:
        insert_at = match.end() + next_section.start()
        prefix = body[:insert_at].rstrip() + "\n"
        suffix = body[insert_at:]
        return prefix + dated_line + "\n\n" + suffix.lstrip("\n")
    return body.rstrip() + "\n" + dated_line + "\n"


def _replace_section(body: str, section_heading: str, lines: list[str]) -> str:
    replacement = f"## {section_heading}\n" + ("\n".join(lines).rstrip() + "\n")
    pattern = rf"(?ms)^##\s+{re.escape(section_heading)}\s*$.*?(?=^##\s+|\Z)"
    if re.search(pattern, body):
        return re.sub(pattern, replacement + "\n", body)
    return body.rstrip() + "\n\n" + replacement


def _new_task_body(
    title: str,
    request: str,
    desired_outcome: str,
    constraints: list[str],
    blocked_reason: str,
) -> str:
    request_lines = request.strip() or "(empty request)"
    outcome_lines = desired_outcome.strip() or "(outcome not specified)"
    constraint_lines = constraints or ["(none recorded)"]
    return "\n".join(
        [
            f"# {title}",
            "",
            "## Request",
            *[f"- {line}" for line in request_lines.splitlines()],
            "",
            "## Desired Outcome",
            *[f"- {line}" for line in outcome_lines.splitlines()],
            "",
            "## Constraints",
            *[f"- {line}" for line in constraint_lines],
            "",
            "## Blocked Reason",
            f"- {blocked_reason.strip() or '(not specified)'}",
            "",
            "## Execution Notes",
            "- Pending pickup.",
            "",
            "## Result",
            "- Pending.",
            "",
        ]
    )


def _all_task_paths(status: str | None = None) -> list[Path]:
    dirs = [STATE_DIRS[status]] if status else list(STATE_DIRS.values())
    out: list[Path] = []
    for directory in dirs:
        out.extend(sorted(directory.glob("*.md")))
    return sorted(out)


def _find_task(path_or_id: str) -> TaskRecord:
    candidate = Path(path_or_id)
    if candidate.exists():
        return _load_task(candidate.resolve())
    for path in _all_task_paths():
        if path.stem == path_or_id or path.name == path_or_id:
            return _load_task(path)
        task = _load_task(path)
        if task.task_id == path_or_id:
            return task
    raise FileNotFoundError(f"Task not found: {path_or_id}")


def _move_task(task: TaskRecord, new_status: str) -> TaskRecord:
    destination = STATE_DIRS[new_status] / task.path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    task.path.replace(destination)
    return _load_task(destination)


def _task_summary(task: TaskRecord) -> dict[str, object]:
    return {
        "id": task.task_id,
        "title": task.title,
        "status": task.status,
        "path": str(task.path.relative_to(REPO_ROOT)),
        "attempt_count": task.attempt_count,
        "max_attempts": task.max_attempts,
        "source": task.meta.get("source", ""),
        "blocked_by": task.meta.get("blocked_by", ""),
        "requested_by": task.meta.get("requested_by", ""),
        "updated_at": task.meta.get("updated_at", ""),
    }


def command_enqueue(args: argparse.Namespace) -> int:
    _ensure_dirs()
    created_at = _now()
    task_id = f"task-{datetime.now().astimezone():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:6]}"
    title = args.title.strip()
    meta: dict[str, object] = {
        "id": task_id,
        "status": "pending",
        "created_at": created_at,
        "updated_at": created_at,
        "source": args.source,
        "requested_by": args.requested_by,
        "chat_id": args.chat_id or "",
        "priority": args.priority,
        "blocked_by": args.blocked_by,
        "worker": "",
        "claimed_at": "",
        "completed_at": "",
        "expires_at": args.expires_at or "",
        "attempt_count": 0,
        "max_attempts": args.max_attempts,
        "parent_task_id": args.parent_task_id or "",
    }
    body = _new_task_body(
        title=title,
        request=args.request,
        desired_outcome=args.desired_outcome,
        constraints=args.constraint or [],
        blocked_reason=args.blocked_reason or args.blocked_by,
    )
    path = STATE_DIRS["pending"] / _task_filename(task_id, title)
    _write_task(path, meta, body)
    task = _load_task(path)
    if args.json:
        print(json.dumps(_task_summary(task), ensure_ascii=False, indent=2))
    else:
        print(f"Enqueued: {path.relative_to(REPO_ROOT)}")
        print(f"Task ID: {task.task_id}")
    return 0


def command_list(args: argparse.Namespace) -> int:
    _ensure_dirs()
    tasks = [_load_task(path) for path in _all_task_paths(status=args.status)]
    if args.json:
        print(
            json.dumps(
                [_task_summary(task) for task in tasks], ensure_ascii=False, indent=2
            )
        )
        return 0
    if not tasks:
        print("No tasks found.")
        return 0
    for task in tasks:
        print(
            f"{task.task_id} | {task.status} | {task.title} | {task.path.relative_to(REPO_ROOT)}"
        )
    return 0


def command_claim_next(args: argparse.Namespace) -> int:
    _ensure_dirs()
    pending = [_load_task(path) for path in sorted(STATE_DIRS["pending"].glob("*.md"))]
    if not pending:
        if args.json:
            print("{}")
        else:
            print("No pending tasks.")
        return 0

    task = pending[0]
    task.meta["status"] = "running"
    task.meta["worker"] = args.worker
    task.meta["claimed_at"] = _now()
    task.meta["updated_at"] = _now()
    task.meta["attempt_count"] = task.attempt_count + 1
    task.body = _append_line(
        task.body, "Execution Notes", f"Claimed by `{args.worker}`."
    )
    _write_task(task.path, task.meta, task.body)
    task = _move_task(_load_task(task.path), "running")
    if args.json:
        print(json.dumps(_task_summary(task), ensure_ascii=False, indent=2))
    else:
        print(f"Claimed: {task.path.relative_to(REPO_ROOT)}")
        print(f"Task ID: {task.task_id}")
    return 0


def command_render_prompt(args: argparse.Namespace) -> int:
    task = _find_task(args.task)
    prompt_lines = [
        "You are processing a deferred task from ChiefOfStuffVault.",
        "Finish the requested work if it is still valid and safe.",
        "When done, summarize the outcome so the queue record can be updated.",
        "Use absolute dates in any user-facing text.",
        "",
        "Task metadata:",
        f"- Task ID: {task.task_id}",
        f"- Status: {task.status}",
        f"- Source: {task.meta.get('source', '')}",
        f"- Requested by: {task.meta.get('requested_by', '')}",
        f"- Blocked by: {task.meta.get('blocked_by', '')}",
        f"- Created at: {task.meta.get('created_at', '')}",
        f"- Attempts: {task.attempt_count}/{task.max_attempts}",
        "",
        "Task record:",
        task.body.rstrip(),
        "",
        "Expected runner behavior:",
        "- If the task is now completable, do the work and prepare a short completion summary.",
        "- If the task is obsolete, explain why and mark it failed without retry.",
        "- If the task is still blocked but may succeed later, record the blocker and keep it retryable.",
    ]
    print("\n".join(prompt_lines).rstrip() + "\n")
    return 0


def _update_terminal_state(
    task: TaskRecord, *, new_status: str, summary: str, retryable: bool
) -> TaskRecord:
    task.meta["updated_at"] = _now()
    if new_status == "done":
        task.meta["status"] = "done"
        task.meta["completed_at"] = _now()
    elif retryable:
        task.meta["status"] = "pending"
        task.meta["worker"] = ""
        task.meta["claimed_at"] = ""
    else:
        task.meta["status"] = "failed"
        task.meta["worker"] = ""
    heading = "Result" if new_status == "done" else "Result"
    marker = "Completed" if new_status == "done" else "Failed"
    task.body = _replace_section(task.body, heading, [f"- {marker}: {summary}"])
    note_text = f"{marker.lower()} with summary: {summary}"
    task.body = _append_line(task.body, "Execution Notes", note_text)
    _write_task(task.path, task.meta, task.body)
    destination_status = (
        "pending" if retryable and new_status != "done" else task.meta["status"]
    )
    return _move_task(_load_task(task.path), str(destination_status))


def command_complete(args: argparse.Namespace) -> int:
    task = _find_task(args.task)
    updated = _update_terminal_state(
        task, new_status="done", summary=args.summary.strip(), retryable=False
    )
    if args.json:
        print(json.dumps(_task_summary(updated), ensure_ascii=False, indent=2))
    else:
        print(f"Completed: {updated.path.relative_to(REPO_ROOT)}")
    return 0


def command_fail(args: argparse.Namespace) -> int:
    task = _find_task(args.task)
    retryable = bool(args.retryable) and task.attempt_count < task.max_attempts
    updated = _update_terminal_state(
        task, new_status="failed", summary=args.summary.strip(), retryable=retryable
    )
    if args.json:
        print(json.dumps(_task_summary(updated), ensure_ascii=False, indent=2))
    else:
        if retryable:
            print(f"Returned to pending: {updated.path.relative_to(REPO_ROOT)}")
        else:
            print(f"Failed: {updated.path.relative_to(REPO_ROOT)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage the deferred task queue for follow-up work that should be handled later."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enqueue = sub.add_parser("enqueue", help="Create a new pending deferred task")
    p_enqueue.add_argument("--title", required=True)
    p_enqueue.add_argument("--source", default="deferred_follow_up")
    p_enqueue.add_argument("--requested-by", required=True)
    p_enqueue.add_argument("--chat-id", default="")
    p_enqueue.add_argument(
        "--priority", default="normal", choices=["low", "normal", "high"]
    )
    p_enqueue.add_argument("--blocked-by", required=True)
    p_enqueue.add_argument("--blocked-reason", default="")
    p_enqueue.add_argument("--request", required=True)
    p_enqueue.add_argument("--desired-outcome", required=True)
    p_enqueue.add_argument("--constraint", action="append")
    p_enqueue.add_argument("--expires-at", default="")
    p_enqueue.add_argument("--max-attempts", type=int, default=3)
    p_enqueue.add_argument("--parent-task-id", default="")
    p_enqueue.add_argument("--json", action="store_true")
    p_enqueue.set_defaults(func=command_enqueue)

    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--status", choices=["pending", "running", "done", "failed"])
    p_list.add_argument("--json", action="store_true")
    p_list.set_defaults(func=command_list)

    p_claim = sub.add_parser(
        "claim-next", help="Move the oldest pending task to running"
    )
    p_claim.add_argument("--worker", required=True)
    p_claim.add_argument("--json", action="store_true")
    p_claim.set_defaults(func=command_claim_next)

    p_render = sub.add_parser(
        "render-prompt", help="Render a deterministic desktop-runner prompt for a task"
    )
    p_render.add_argument("--task", required=True)
    p_render.set_defaults(func=command_render_prompt)

    p_complete = sub.add_parser("complete", help="Mark a task as done")
    p_complete.add_argument("--task", required=True)
    p_complete.add_argument("--summary", required=True)
    p_complete.add_argument("--json", action="store_true")
    p_complete.set_defaults(func=command_complete)

    p_fail = sub.add_parser(
        "fail", help="Mark a task as failed or return it to pending"
    )
    p_fail.add_argument("--task", required=True)
    p_fail.add_argument("--summary", required=True)
    p_fail.add_argument("--retryable", action="store_true")
    p_fail.add_argument("--json", action="store_true")
    p_fail.set_defaults(func=command_fail)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
