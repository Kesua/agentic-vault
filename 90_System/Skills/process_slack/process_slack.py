from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MAILBOX_DIR = REPO_ROOT / "00_Mailbox"
TEMPLATE_DIR = MAILBOX_DIR / "Templates"
SUMMARY_TEMPLATE_PATH = TEMPLATE_DIR / "SlackSummary_TEMPLATE.md"
THREAD_TEMPLATE_PATH = TEMPLATE_DIR / "SlackThread_TEMPLATE.md"
SLACK_SKILL_DIR = Path(__file__).resolve().parents[1] / "slack_assistant"

if str(SLACK_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(SLACK_SKILL_DIR))

import slack_assistant as sa  # noqa: E402


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


def _target_day_path(day_value: datetime) -> Path:
    return (
        MAILBOX_DIR
        / day_value.strftime("%Y")
        / day_value.strftime("%m")
        / day_value.strftime("%d")
    )


def _summary_path(day_value: datetime) -> Path:
    target_dir = _target_day_path(day_value)
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "slack_summary.md"


def _thread_path(thread: sa.ConversationThread) -> Path:
    latest_dt = sa._message_dt(thread.messages[-1].ts)
    target_dir = _target_day_path(latest_dt)
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = sa._sanitize_filename(
        f"slack_{thread.workspace}_{thread.conversation.name}_{thread.root_ts.replace('.', '_')}"
    )
    return target_dir / f"{filename}.md"


def _render_summary(
    day_threads: list[sa.ConversationThread], *, window_label: str
) -> str:
    if not SUMMARY_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Missing template: {SUMMARY_TEMPLATE_PATH}")
    generated_at = datetime.now(sa.PRAGUE_TZ).isoformat(timespec="minutes")
    thread_lines: list[str] = []
    if not day_threads:
        thread_lines.append("- No Slack activity exported.")
    else:
        for thread in day_threads:
            latest = thread.messages[-1]
            preview = re.sub(r"\s+", " ", latest.text).strip()[:240] or "(No text)"
            participants = ", ".join(
                sa._dedupe_preserve_order(
                    [message.user_id for message in thread.messages if message.user_id]
                )
            )
            thread_lines.extend(
                [
                    f"- `{sa._message_dt(latest.ts).isoformat(timespec='minutes')}` [{thread.workspace}] {thread.conversation.name}",
                    f"  - Thread: `{thread.root_ts}`",
                    f"  - Kind: {thread.conversation.kind}",
                    f"  - Participants: {participants or '(unknown)'}",
                    f"  - Retention: {thread.conversation.retention_class}",
                    f"  - Summary: {preview}",
                ]
            )
    rendered = SUMMARY_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{generated_at}}": generated_at,
        "{{window_label}}": window_label,
        "{{thread_count}}": str(len(day_threads)),
        "{{threads_block}}": "\n".join(thread_lines).rstrip(),
    }
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, value)
    return rendered


def _thread_frontmatter(path: Path) -> dict[str, object]:
    return sa._parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))


def _remove_older_instances(
    thread: sa.ConversationThread, keep_path: Path, dry_run: bool
) -> int:
    removed = 0
    for path in MAILBOX_DIR.rglob("*.md"):
        if path == keep_path or path.name in {
            "_Mailbox.md",
            "emails_summary.md",
            "slack_summary.md",
        }:
            continue
        metadata = _thread_frontmatter(path)
        if str(metadata.get("source", "")).strip() != "slack":
            continue
        if str(metadata.get("workspace", "")).strip() != thread.workspace:
            continue
        if str(metadata.get("conversation_id", "")).strip() != thread.conversation.id:
            continue
        if str(metadata.get("thread_ts", "")).strip() != thread.root_ts:
            continue
        removed += 1
        if dry_run:
            print(f"Would remove older Slack snapshot: {path}")
        else:
            path.unlink()
            print(f"Removed older Slack snapshot: {path}")
    return removed


def _render_thread(thread: sa.ConversationThread) -> str:
    if not THREAD_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Missing template: {THREAD_TEMPLATE_PATH}")
    client = sa.SlackClient(sa.get_workspace_config(thread.workspace))
    user_map = client.users()
    by_email, by_alias = sa.people_lookup()
    participants = sa._dedupe_preserve_order(
        [
            sa._user_label(user_map, message)
            for message in thread.messages
            if sa._is_human_message(message)
        ]
    )
    participant_yaml = (
        "\n".join(f"  - {sa._yaml_quote(item)}" for item in participants)
        if participants
        else '  - ""'
    )
    linked_people_raw: list[str] = []
    for message in thread.messages:
        match = sa.find_matching_person(user_map, message, by_email, by_alias)
        if match:
            linked_people_raw.append(match)
    linked_people = sa._dedupe_preserve_order(linked_people_raw)
    linked_people_block = (
        ", ".join(f"[[{item}]]" for item in linked_people) if linked_people else ""
    )
    message_lines: list[str] = []
    for message in thread.messages:
        when = sa._message_dt(message.ts).isoformat(timespec="minutes")
        sender = sa._user_label(user_map, message)
        reactions = ", ".join(message.reactions)
        files = ", ".join(file.name for file in message.files)
        status_bits = []
        if message.edited:
            status_bits.append("edited")
        if message.deleted:
            status_bits.append("deleted")
        status = ", ".join(status_bits) or "normal"
        message_lines.extend(
            [
                f"### {when} - {sender}",
                f"- Status: {status}",
                f"- Slack user: {message.user_id or '(unknown)'}",
                f"- Reactions: {reactions or '(none)'}",
                f"- Files: {files or '(none)'}",
                "",
                message.text.strip() or "(No text)",
                "",
            ]
        )
    rendered = THREAD_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{workspace}}": thread.workspace,
        "{{team_id}}": thread.team_id,
        "{{conversation_id}}": thread.conversation.id,
        "{{conversation_name}}": thread.conversation.name,
        "{{conversation_kind}}": thread.conversation.kind,
        "{{thread_ts}}": thread.root_ts,
        "{{last_message_at}}": sa._message_dt(thread.messages[-1].ts).isoformat(
            timespec="minutes"
        ),
        "{{stored_at}}": datetime.now(sa.PRAGUE_TZ).isoformat(timespec="minutes"),
        "{{retention_class}}": thread.conversation.retention_class,
        "{{permalink}}": thread.permalink,
        "{{participants_yaml}}": participant_yaml,
        "{{participants_inline}}": ", ".join(participants),
        "{{linked_people}}": linked_people_block,
        "{{messages_block}}": "\n".join(message_lines).rstrip(),
    }
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, value)
    return rendered


def _workspace_names(arg_value: str) -> list[str]:
    configs = sa.load_workspace_configs()
    if arg_value == "all":
        return sorted(configs)
    if arg_value not in configs:
        raise RuntimeError(
            f"Unknown workspace alias '{arg_value}'. Configured: {', '.join(sorted(configs))}"
        )
    return [arg_value]


def _conversation_filter(
    workspace: sa.WorkspaceConfig, include_dm: bool, include_mpim: bool
) -> set[str]:
    allowed = set()
    for conversation in workspace.allow_conversations:
        if conversation.kind == "im" and not include_dm:
            continue
        if conversation.kind == "mpim" and not include_mpim:
            continue
        allowed.add(conversation.id)
    return allowed


def _sync_threads_for_workspace(
    workspace_alias: str,
    *,
    days_back: int | None,
    dry_run: bool,
    include_dm: bool,
    include_mpim: bool,
) -> tuple[int, int]:
    workspace = sa.get_workspace_config(workspace_alias)
    allowed = _conversation_filter(workspace, include_dm, include_mpim)
    state = sa.load_runtime_state(workspace_alias)
    conversation_state = state.setdefault("conversations", {})
    explicit_oldest = (
        sa._days_back_to_oldest(days_back, default_days=3)
        if days_back is not None
        else None
    )
    known_timestamps = [
        str(conversation_state.get(conversation.id, {}).get("last_ts") or "").strip()
        for conversation in workspace.allow_conversations
        if conversation.id in allowed
    ]
    valid_timestamps = [value for value in known_timestamps if value]
    oldest = explicit_oldest or min(
        valid_timestamps + [sa._days_back_to_oldest(None, default_days=3)]
    )
    threads = sa.collect_threads(workspace, oldest=oldest, conversation_ids=allowed)
    written = 0
    removed = 0
    for thread in threads:
        path = _thread_path(thread)
        removed += _remove_older_instances(thread, path, dry_run)
        if dry_run:
            print(f"Would write Slack thread snapshot: {path}")
        else:
            path.write_text(_render_thread(thread), encoding="utf-8")
            print(f"Wrote Slack thread snapshot: {path}")
            conversation_state[thread.conversation.id] = {
                "last_ts": thread.messages[-1].ts,
                "last_thread_ts": thread.root_ts,
                "last_synced_at": datetime.now(sa.PRAGUE_TZ).isoformat(
                    timespec="seconds"
                ),
            }
        written += 1
    if not dry_run:
        sa.save_runtime_state(workspace_alias, state)
    return written, removed


def command_sync_threads(args: argparse.Namespace) -> None:
    total_written = 0
    total_removed = 0
    for workspace_alias in _workspace_names(args.workspace):
        written, removed = _sync_threads_for_workspace(
            workspace_alias,
            days_back=args.days_back,
            dry_run=args.dry_run,
            include_dm=args.include_dm,
            include_mpim=args.include_mpim,
        )
        total_written += written
        total_removed += removed
    print(f"Slack thread snapshots: {total_written}")
    print(f"Older Slack instances removed: {total_removed}")


def _sync_summary_for_workspace(
    workspace_alias: str,
    *,
    days_back: int | None,
    dry_run: bool,
    include_dm: bool,
    include_mpim: bool,
) -> int:
    workspace = sa.get_workspace_config(workspace_alias)
    allowed = _conversation_filter(workspace, include_dm, include_mpim)
    oldest = sa._days_back_to_oldest(days_back, default_days=1)
    threads = sa.collect_threads(workspace, oldest=oldest, conversation_ids=allowed)
    grouped: dict[str, list[sa.ConversationThread]] = defaultdict(list)
    for thread in threads:
        grouped[sa._message_dt(thread.messages[-1].ts).date().isoformat()].append(
            thread
        )
    if not grouped:
        path = _summary_path(datetime.now(sa.PRAGUE_TZ))
        if dry_run:
            print(f"Would write Slack summary: {path}")
        else:
            path.write_text(
                _render_summary([], window_label=f"last {(days_back or 1)} day(s)"),
                encoding="utf-8",
            )
            print(f"Wrote Slack summary: {path}")
        return 0
    count = 0
    for day_key in sorted(grouped):
        day_dt = datetime.fromisoformat(f"{day_key}T00:00:00").replace(
            tzinfo=sa.PRAGUE_TZ
        )
        path = _summary_path(day_dt)
        if dry_run:
            print(f"Would write Slack summary: {path}")
        else:
            path.write_text(
                _render_summary(
                    grouped[day_key], window_label=f"last {(days_back or 1)} day(s)"
                ),
                encoding="utf-8",
            )
            print(f"Wrote Slack summary: {path}")
        count += len(grouped[day_key])
    return count


def command_sync_summary(args: argparse.Namespace) -> None:
    total = 0
    for workspace_alias in _workspace_names(args.workspace):
        total += _sync_summary_for_workspace(
            workspace_alias,
            days_back=args.days_back,
            dry_run=args.dry_run,
            include_dm=args.include_dm,
            include_mpim=args.include_mpim,
        )
    print(f"Slack summary threads: {total}")


def command_sync(args: argparse.Namespace) -> None:
    command_sync_summary(args)
    command_sync_threads(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Export Slack summaries and thread snapshots into 00_Mailbox."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser(
        "sync", help="Run both Slack summary and thread snapshot export"
    )
    p_sync.add_argument("--workspace", default="all")
    p_sync.add_argument("--days-back", type=int, default=None)
    p_sync.add_argument("--dry-run", action="store_true")
    p_sync.add_argument("--include-dm", action="store_true")
    p_sync.add_argument("--include-mpim", action="store_true")
    p_sync.set_defaults(func=command_sync)

    p_summary = sub.add_parser("sync-summary", help="Write Slack daily summary notes")
    p_summary.add_argument("--workspace", default="all")
    p_summary.add_argument("--days-back", type=int, default=None)
    p_summary.add_argument("--dry-run", action="store_true")
    p_summary.add_argument("--include-dm", action="store_true")
    p_summary.add_argument("--include-mpim", action="store_true")
    p_summary.set_defaults(func=command_sync_summary)

    p_threads = sub.add_parser("sync-threads", help="Write Slack thread snapshot notes")
    p_threads.add_argument("--workspace", default="all")
    p_threads.add_argument("--days-back", type=int, default=None)
    p_threads.add_argument("--dry-run", action="store_true")
    p_threads.add_argument("--include-dm", action="store_true")
    p_threads.add_argument("--include-mpim", action="store_true")
    p_threads.set_defaults(func=command_sync_threads)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
    except (RuntimeError, FileNotFoundError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
