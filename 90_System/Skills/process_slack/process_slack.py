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
    return MAILBOX_DIR / day_value.strftime("%Y") / day_value.strftime("%m") / day_value.strftime("%d")


def _summary_path(day_value: datetime) -> Path:
    target_dir = _target_day_path(day_value)
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "slack_summary.md"


def _thread_path(thread: sa.ConversationThread) -> Path:
    latest_dt = sa._message_dt(thread.messages[-1].ts)
    target_dir = _target_day_path(latest_dt)
    target_dir.mkdir(parents=True, exist_ok=True)
    conversation_slug = thread.conversation.name
    if thread.conversation.kind in sa.DM_KINDS:
        conversation_slug = f"{thread.conversation.name}_{thread.conversation.id}"
    filename = sa._sanitize_filename(
        f"slack_{thread.workspace}_{conversation_slug}_{thread.root_ts.replace('.', '_')}"
    )
    return target_dir / f"{filename}.md"


def _thread_key(thread: sa.ConversationThread) -> tuple[str, str, str]:
    return (thread.workspace, thread.conversation.id, thread.root_ts)


def _render_summary(day_threads: list[sa.ConversationThread], *, window_label: str) -> str:
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


def _thread_key_from_metadata(metadata: dict[str, object]) -> tuple[str, str, str] | None:
    if str(metadata.get("source", "")).strip() != "slack":
        return None
    workspace = str(metadata.get("workspace", "")).strip()
    conversation_id = str(metadata.get("conversation_id", "")).strip()
    thread_ts = str(metadata.get("thread_ts", "")).strip()
    if not workspace or not conversation_id or not thread_ts:
        return None
    return (workspace, conversation_id, thread_ts)


def _build_thread_index() -> dict[tuple[str, str, str], list[Path]]:
    index: dict[tuple[str, str, str], list[Path]] = defaultdict(list)
    for path in MAILBOX_DIR.rglob("slack_*.md"):
        if path.name == "slack_summary.md":
            continue
        key = _thread_key_from_metadata(_thread_frontmatter(path))
        if key is not None:
            index[key].append(path)
    return index


def _remove_older_instances(
    thread: sa.ConversationThread,
    keep_path: Path,
    dry_run: bool,
    thread_index: dict[tuple[str, str, str], list[Path]],
) -> int:
    removed = 0
    key = _thread_key(thread)
    existing_paths = list(thread_index.get(key, []))
    kept_paths: list[Path] = []
    for path in existing_paths:
        if path == keep_path:
            kept_paths.append(path)
            continue
        removed += 1
        if dry_run:
            print(f"Would remove older Slack snapshot: {path}")
        else:
            path.unlink()
            print(f"Removed older Slack snapshot: {path}")
    thread_index[key] = kept_paths
    return removed


def _write_text_if_changed(path: Path, content: str, *, dry_run: bool, write_label: str, unchanged_label: str) -> bool:
    existing = None
    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="replace")
    if existing == content:
        print(f"{unchanged_label}: {path}")
        return False
    if dry_run:
        print(f"Would write {write_label}: {path}")
        return True
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {write_label}: {path}")
    return True


def _normalize_summary_for_compare(content: str) -> str:
    lines = []
    for line in content.splitlines():
        if line.startswith("generated_at: "):
            continue
        if line.startswith("- Generated: "):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _write_summary_if_changed(path: Path, content: str, *, dry_run: bool) -> bool:
    if path.exists():
        existing = path.read_text(encoding="utf-8", errors="replace")
        if _normalize_summary_for_compare(existing) == _normalize_summary_for_compare(content):
            print(f"Slack summary unchanged: {path}")
            return False
    if dry_run:
        print(f"Would write Slack summary: {path}")
        return True
    path.write_text(content, encoding="utf-8")
    print(f"Wrote Slack summary: {path}")
    return True


def _history_cursor_from_state(record: dict[str, object], default_oldest: str) -> str:
    explicit_cursor = str(record.get("history_cursor_ts") or "").strip()
    if explicit_cursor:
        return explicit_cursor
    last_synced_at = str(record.get("last_synced_at") or "").strip()
    if last_synced_at:
        try:
            return f"{datetime.fromisoformat(last_synced_at).timestamp():.6f}"
        except ValueError:
            pass
    last_ts = str(record.get("last_ts") or "").strip()
    if last_ts:
        return last_ts
    return default_oldest


def _render_thread(thread: sa.ConversationThread) -> str:
    if not THREAD_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Missing template: {THREAD_TEMPLATE_PATH}")
    workspace = sa.get_workspace_config(thread.workspace)
    user_map = sa.merged_user_map(workspace, preferred_source=thread.conversation.auth_source)
    by_email, by_alias = sa.people_lookup()
    participants = sa._dedupe_preserve_order(
        [sa._user_label(user_map, message) for message in thread.messages if sa._is_human_message(message)]
    )
    participant_yaml = "\n".join(f"  - {sa._yaml_quote(item)}" for item in participants) if participants else '  - ""'
    linked_people_raw: list[str] = []
    for message in thread.messages:
        match = sa.find_matching_person(user_map, message, by_email, by_alias)
        if match:
            linked_people_raw.append(match)
    linked_people = sa._dedupe_preserve_order(linked_people_raw)
    linked_people_block = ", ".join(f"[[{item}]]" for item in linked_people) if linked_people else ""
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
        "{{last_message_at}}": sa._message_dt(thread.messages[-1].ts).isoformat(timespec="minutes"),
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
        raise RuntimeError(f"Unknown workspace alias '{arg_value}'. Configured: {', '.join(sorted(configs))}")
    return [arg_value]


def _conversation_filter(workspace: sa.WorkspaceConfig, include_dm: bool, include_mpim: bool) -> set[str]:
    return {
        conversation.id
        for conversation in sa.workspace_conversations(
            workspace,
            include_channels=True,
            include_dm=include_dm,
            include_mpim=include_mpim,
        )
    }


def _sync_threads_for_workspace(
    workspace_alias: str,
    *,
    days_back: int | None,
    dry_run: bool,
    include_dm: bool,
    include_mpim: bool,
    thread_index: dict[tuple[str, str, str], list[Path]],
) -> tuple[int, int]:
    workspace = sa.get_workspace_config(workspace_alias)
    conversations = sa.workspace_conversations(
        workspace,
        include_channels=True,
        include_dm=include_dm,
        include_mpim=include_mpim,
    )
    state = sa.load_runtime_state(workspace_alias)
    conversation_state = state.setdefault("conversations", {})
    default_oldest = sa._days_back_to_oldest(None, default_days=3)
    explicit_oldest = sa._days_back_to_oldest(days_back, default_days=3) if days_back is not None else None
    deduped: dict[tuple[str, str], sa.ConversationThread] = {}
    latest_seen_by_conversation: dict[str, str] = {}
    conversation_meta = {conversation.id: conversation for conversation in conversations}
    for conversation in conversations:
        sync_started_ts = f"{datetime.now(sa.PRAGUE_TZ).timestamp():.6f}"
        conversation_record = conversation_state.get(conversation.id, {})
        conversation_oldest = (
            explicit_oldest
            or _history_cursor_from_state(conversation_record, default_oldest)
        )
        client = sa.get_client_for_conversation(workspace, conversation)
        try:
            history = client.conversation_history(conversation.id, oldest=conversation_oldest)
        except RuntimeError as exc:
            sa.warn_conversation_error(workspace, conversation, exc)
            continue
        latest_seen_by_conversation[conversation.id] = sync_started_ts
        for root in sa._root_candidates(history, conversation):
            try:
                messages = sa._thread_messages(client, conversation, root)
            except RuntimeError as exc:
                sa.warn_conversation_error(workspace, conversation, exc)
                continue
            if not messages:
                continue
            try:
                permalink = client.permalink(conversation.id, messages[0].thread_ts or messages[0].ts)
            except RuntimeError as exc:
                sa.warn_conversation_error(workspace, conversation, exc)
                permalink = ""
            thread = sa.ConversationThread(
                workspace=workspace.alias,
                team_id=workspace.team_id,
                conversation=conversation,
                root_ts=messages[0].thread_ts or messages[0].ts,
                permalink=permalink,
                messages=tuple(messages),
            )
            key = (thread.conversation.id, thread.root_ts)
            existing = deduped.get(key)
            if existing is None or float(thread.messages[-1].ts) > float(existing.messages[-1].ts):
                deduped[key] = thread
            if float(thread.messages[-1].ts) > float(latest_seen_by_conversation[conversation.id]):
                latest_seen_by_conversation[conversation.id] = thread.messages[-1].ts
    threads = sorted(deduped.values(), key=lambda item: float(item.messages[-1].ts), reverse=True)
    written = 0
    removed = 0
    for thread in threads:
        path = _thread_path(thread)
        removed += _remove_older_instances(thread, path, dry_run, thread_index)
        content = _render_thread(thread)
        did_write = _write_text_if_changed(
            path,
            content,
            dry_run=dry_run,
            write_label="Slack thread snapshot",
            unchanged_label="Slack thread snapshot unchanged",
        )
        if path not in thread_index[_thread_key(thread)]:
            thread_index[_thread_key(thread)].append(path)
        conversation_state[thread.conversation.id] = {
            "auth_source": thread.conversation.auth_source,
            "kind": thread.conversation.kind,
            "name": thread.conversation.name,
            "last_ts": thread.messages[-1].ts,
            "last_thread_ts": thread.root_ts,
            "history_cursor_ts": latest_seen_by_conversation.get(thread.conversation.id, thread.messages[-1].ts),
            "last_synced_at": datetime.now(sa.PRAGUE_TZ).isoformat(timespec="seconds"),
        }
        if did_write:
            written += 1
    for conversation_id, latest_seen_ts in latest_seen_by_conversation.items():
        record = conversation_state.setdefault(conversation_id, {})
        conversation = conversation_meta.get(conversation_id)
        if conversation is not None:
            record["auth_source"] = conversation.auth_source
            record["kind"] = conversation.kind
            record["name"] = conversation.name
        record["history_cursor_ts"] = latest_seen_ts
        record["last_synced_at"] = datetime.now(sa.PRAGUE_TZ).isoformat(timespec="seconds")
    if not dry_run:
        sa.save_runtime_state(workspace_alias, state)
    return written, removed


def command_sync_threads(args: argparse.Namespace) -> None:
    total_written = 0
    total_removed = 0
    thread_index = _build_thread_index()
    for workspace_alias in _workspace_names(args.workspace):
        written, removed = _sync_threads_for_workspace(
            workspace_alias,
            days_back=args.days_back,
            dry_run=args.dry_run,
            include_dm=args.include_dm,
            include_mpim=args.include_mpim,
            thread_index=thread_index,
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
    oldest = sa._days_back_to_oldest(days_back, default_days=1)
    threads = sa.collect_threads(
        workspace,
        oldest=oldest,
        conversation_ids=_conversation_filter(workspace, include_dm, include_mpim),
        include_dm=include_dm,
        include_mpim=include_mpim,
    )
    grouped: dict[str, list[sa.ConversationThread]] = defaultdict(list)
    for thread in threads:
        grouped[sa._message_dt(thread.messages[-1].ts).date().isoformat()].append(thread)
    if not grouped:
        path = _summary_path(datetime.now(sa.PRAGUE_TZ))
        _write_summary_if_changed(
            path,
            _render_summary([], window_label=f"last {(days_back or 1)} day(s)"),
            dry_run=dry_run,
        )
        return 0
    count = 0
    for day_key in sorted(grouped):
        day_dt = datetime.fromisoformat(f"{day_key}T00:00:00").replace(tzinfo=sa.PRAGUE_TZ)
        path = _summary_path(day_dt)
        _write_summary_if_changed(
            path,
            _render_summary(grouped[day_key], window_label=f"last {(days_back or 1)} day(s)"),
            dry_run=dry_run,
        )
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
    parser = argparse.ArgumentParser(description="Export Slack summaries and thread snapshots into 00_Mailbox.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Run both Slack summary and thread snapshot export")
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
