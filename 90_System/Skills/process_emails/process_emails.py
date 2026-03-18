from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MAILBOX_DIR = REPO_ROOT / "00_Mailbox"
TEMPLATE_DIR = MAILBOX_DIR / "Templates"
THREAD_TEMPLATE_PATH = TEMPLATE_DIR / "EmailThread_TEMPLATE.md"
SUMMARY_TEMPLATE_PATH = TEMPLATE_DIR / "EmailSummary_TEMPLATE.md"
GMAIL_SKILL_DIR = Path(__file__).resolve().parents[1] / "gmail_assistant"

if str(GMAIL_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(GMAIL_SKILL_DIR))

import gmail_assistant as ga  # noqa: E402


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


def _sanitize_filename(text: str) -> str:
    text = re.sub(r'[<>:"/\\\\|?*]+', "-", text.strip())
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return text[:120] if text else "Untitled"


def _target_day_path(day_value: datetime) -> Path:
    return MAILBOX_DIR / day_value.strftime("%Y") / day_value.strftime("%m") / day_value.strftime("%d")


def _frontmatter(text: str) -> dict[str, object]:
    match = re.match(r"(?s)^\ufeff?---\r?\n(.*?)\r?\n---\r?\n?", text)
    if not match:
        return {}
    data: dict[str, object] = {}
    key: str | None = None
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        list_match = re.match(r"^\s*-\s+(.*)$", line)
        if list_match and key:
            data.setdefault(key, [])
            if isinstance(data[key], list):
                data[key].append(_yaml_unquote(list_match.group(1).strip()))
            continue
        kv_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not kv_match:
            continue
        key = kv_match.group(1)
        raw_value = kv_match.group(2).strip()
        data[key] = _yaml_unquote(raw_value) if raw_value else []
    return data


def _yaml_unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalized = value.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _important_cutoff() -> datetime:
    return datetime.now().astimezone() - timedelta(hours=24)


def _sent_cutoff() -> datetime:
    return datetime.now().astimezone() - timedelta(hours=72)


def _days_back_value(raw_value: int | None, default_days: int) -> int:
    if raw_value is None:
        return default_days
    if raw_value < 1:
        raise ValueError("--days-back must be >= 1")
    return raw_value


def _cutoff_from_days(days_back: int) -> datetime:
    return datetime.now().astimezone() - timedelta(days=days_back)


def _message_metadata(message: ga.GmailMessage) -> tuple[str, str]:
    sender = message.from_name or message.from_email or "unknown"
    subject = message.subject or "(No subject)"
    return sender, subject


def _summary_path(day_value: datetime) -> Path:
    target_dir = _target_day_path(day_value)
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / "emails_summary.md"


def _important_messages_for_account(account: str, *, days_back: int) -> list[tuple[ga.GmailMessage, str]]:
    service = ga._gmail_service(account)
    thread_ids = ga._gmail_list_threads(service, f"label:important newer_than:{days_back}d", max_results=500)
    cutoff = _cutoff_from_days(days_back)
    items: list[tuple[ga.GmailMessage, str]] = []
    for thread_id in thread_ids:
        for message in ga._get_thread_messages(service, thread_id):
            message_dt = ga._message_datetime(message)
            if message_dt < cutoff:
                continue
            if "IMPORTANT" not in message.label_ids:
                continue
            items.append((message, account))
    return sorted(items, key=lambda item: ga._message_datetime(item[0]), reverse=True)


def _render_summary(messages: list[tuple[ga.GmailMessage, str]], *, window_label: str) -> str:
    if not SUMMARY_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Missing template: {SUMMARY_TEMPLATE_PATH}")
    generated_at = datetime.now().astimezone().isoformat(timespec="minutes")
    message_lines: list[str] = []
    if not messages:
        message_lines.append("- No important emails found.")
    else:
        for message, account in messages:
            message_dt = ga._message_datetime(message).isoformat(timespec="minutes")
            sender, subject = _message_metadata(message)
            snippet = ga._clip_text(message.body_text or message.snippet, 240)
            message_lines.extend(
                [
                    f"- `{message_dt}` [{account}] {sender} - {subject}",
                    f"  - Thread: `{message.thread_id}`",
                    f"  - Project: ",
                    f"  - Summary: {snippet or '(No snippet)'}",
                ]
            )

    rendered = SUMMARY_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{generated_at}}": generated_at,
        "{{window_label}}": window_label,
        "{{message_count}}": str(len(messages)),
        "{{messages_block}}": "\n".join(message_lines).rstrip(),
    }
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, value)
    return rendered


def command_sync_important(args: argparse.Namespace) -> None:
    days_back = _days_back_value(args.days_back, default_days=1)
    all_messages: list[tuple[ga.GmailMessage, str]] = []
    for account in ("private", "personal"):
        all_messages.extend(_important_messages_for_account(account, days_back=days_back))
    all_messages.sort(key=lambda item: ga._message_datetime(item[0]), reverse=True)

    grouped: dict[str, list[tuple[ga.GmailMessage, str]]] = {}
    for item in all_messages:
        key = ga._message_datetime(item[0]).date().isoformat()
        grouped.setdefault(key, []).append(item)

    if not grouped:
        path = _summary_path(datetime.now().astimezone())
        if args.dry_run:
            print(f"Would write summary: {path}")
        else:
            path.write_text(_render_summary([], window_label=f"last {days_back} day(s)"), encoding="utf-8")
            print(f"Wrote summary: {path}")
        print("Important messages: 0")
        return

    for day_key in sorted(grouped):
        day_date = date.fromisoformat(day_key)
        day_value = datetime.combine(day_date, time.min).astimezone()
        path = _summary_path(day_value)
        if args.dry_run:
            print(f"Would write summary: {path}")
        else:
            path.write_text(_render_summary(grouped[day_key], window_label=f"last {days_back} day(s)"), encoding="utf-8")
            print(f"Wrote summary: {path}")
    print(f"Important messages: {len(all_messages)}")


def _thread_has_sent_message(messages: list[ga.GmailMessage], my_email: str, cutoff: datetime) -> bool:
    for message in messages:
        if message.from_email != my_email:
            continue
        if ga._message_datetime(message) >= cutoff:
            return True
    return False


def _thread_path(account: str, latest_message: ga.GmailMessage) -> Path:
    latest_dt = ga._message_datetime(latest_message)
    target_dir = _target_day_path(latest_dt)
    target_dir.mkdir(parents=True, exist_ok=True)
    name = _sanitize_filename(f"{latest_message.thread_id}_{latest_message.subject}")
    return target_dir / f"{name}.md"


def _render_thread(messages: list[ga.GmailMessage], account: str) -> str:
    if not THREAD_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Missing template: {THREAD_TEMPLATE_PATH}")
    latest = messages[-1]
    latest_at = ga._message_datetime(latest)
    participants = _dedupe_preserve_order(
        [msg.from_email for msg in messages if msg.from_email]
        + [email_addr for msg in messages for email_addr in msg.to_emails]
        + [email_addr for msg in messages for email_addr in msg.cc_emails]
    )
    emails_block = "\n".join(f"  - {_yaml_quote(item)}" for item in participants) if participants else '  - ""'
    body_lines: list[str] = []
    for message in messages:
        when = ga._message_datetime(message).isoformat(timespec="minutes")
        sender = message.from_name or message.from_email or "unknown"
        to_line = ", ".join(message.to_emails) if message.to_emails else ""
        cc_line = ", ".join(message.cc_emails) if message.cc_emails else ""
        body_lines.extend(
            [
                f"### {when} - {sender}",
                f"- From: {message.from_email or sender}",
                f"- To: {to_line}",
                f"- Cc: {cc_line}",
                f"- Subject: {message.subject}",
                "",
                message.body_text.strip() or message.snippet or "(No body)",
                "",
            ]
        )

    rendered = THREAD_TEMPLATE_PATH.read_text(encoding="utf-8")
    replacements = {
        "{{account}}": account,
        "{{thread_id}}": latest.thread_id,
        "{{subject}}": latest.subject,
        "{{last_message_at}}": latest_at.isoformat(timespec="minutes"),
        "{{stored_at}}": datetime.now().astimezone().isoformat(timespec="minutes"),
        "{{emails_yaml}}": emails_block,
        "{{participants_inline}}": ", ".join(participants),
        "{{messages_block}}": "\n".join(body_lines).rstrip(),
    }
    for needle, value in replacements.items():
        rendered = rendered.replace(needle, value)
    return rendered


def _remove_older_instances(account: str, thread_id: str, keep_path: Path, dry_run: bool) -> int:
    removed = 0
    for path in MAILBOX_DIR.rglob("*.md"):
        if path == keep_path or path.name in {"_Mailbox.md", "emails_summary.md"}:
            continue
        metadata = _frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if str(metadata.get("thread_id", "")).strip() != thread_id:
            continue
        if str(metadata.get("account", "")).strip() != account:
            continue
        removed += 1
        if dry_run:
            print(f"Would remove older thread snapshot: {path}")
        else:
            path.unlink()
            print(f"Removed older thread snapshot: {path}")
    return removed


def _sent_threads_for_account(account: str, *, days_back: int) -> list[tuple[list[ga.GmailMessage], str]]:
    service = ga._gmail_service(account)
    my_email = ga._get_profile_email(service)
    cutoff = _cutoff_from_days(days_back)
    thread_ids = ga._gmail_list_threads(service, f"in:anywhere from:me newer_than:{days_back}d", max_results=500)
    items: list[tuple[list[ga.GmailMessage], str]] = []
    seen: set[str] = set()
    for thread_id in thread_ids:
        if thread_id in seen:
            continue
        seen.add(thread_id)
        messages = ga._get_thread_messages(service, thread_id)
        if not messages or not _thread_has_sent_message(messages, my_email, cutoff):
            continue
        items.append((messages, account))
    return items


def command_sync_sent_threads(args: argparse.Namespace) -> None:
    days_back = _days_back_value(args.days_back, default_days=3)
    thread_sets: list[tuple[list[ga.GmailMessage], str]] = []
    for account in ("private", "personal"):
        thread_sets.extend(_sent_threads_for_account(account, days_back=days_back))

    written = 0
    removed = 0
    for messages, account in sorted(thread_sets, key=lambda item: ga._message_datetime(item[0][-1]), reverse=True):
        latest = messages[-1]
        path = _thread_path(account, latest)
        removed += _remove_older_instances(account, latest.thread_id, path, dry_run=args.dry_run)
        if args.dry_run:
            print(f"Would write thread snapshot: {path}")
        else:
            path.write_text(_render_thread(messages, account), encoding="utf-8")
            print(f"Wrote thread snapshot: {path}")
        written += 1

    print(f"Thread snapshots: {written}")
    print(f"Older instances removed: {removed}")


def command_sync(args: argparse.Namespace) -> None:
    command_sync_important(args)
    command_sync_sent_threads(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch-process email summaries and thread snapshots into 00_Mailbox.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Run both important-email summary and sent-thread snapshot export")
    p_sync.add_argument("--dry-run", action="store_true")
    p_sync.add_argument("--days-back", type=int, default=None, help="Backfill this many days for both exports")
    p_sync.set_defaults(func=command_sync)

    p_imp = sub.add_parser("sync-important", help="Write the last 24h important-email summary")
    p_imp.add_argument("--dry-run", action="store_true")
    p_imp.add_argument("--days-back", type=int, default=None, help="Backfill this many days of important emails")
    p_imp.set_defaults(func=command_sync_important)

    p_threads = sub.add_parser("sync-sent-threads", help="Write latest snapshots for threads you sent in over the last 72h")
    p_threads.add_argument("--dry-run", action="store_true")
    p_threads.add_argument("--days-back", type=int, default=None, help="Backfill this many days of sent-thread snapshots")
    p_threads.set_defaults(func=command_sync_sent_threads)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
