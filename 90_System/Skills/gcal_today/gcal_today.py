from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
OAUTH_CLIENT_PRIVATE_PATH = SECRETS_DIR / "gcal_oauth_client_private.json"
OAUTH_CLIENT_PERSONAL_PATH = SECRETS_DIR / "gcal_oauth_client_personal.json"
OAUTH_CLIENT_SHARED_PATH = SECRETS_DIR / "gcal_oauth_client.json"
TOKEN_PRIVATE_PATH = SECRETS_DIR / "gcal_token_private.json"
TOKEN_PERSONAL_PATH = SECRETS_DIR / "gcal_token_personal.json"

MEETING_TEMPLATE_PATH = (
    REPO_ROOT / "20_Meetings" / "Templates" / "MeetingNote_TEMPLATE.md"
)
MEETING_INDEX_PATH = REPO_ROOT / "20_Meetings" / "_MeetingIndex.md"


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


@dataclass(frozen=True)
class CalendarEvent:
    key: str  # Stable per occurrence (instance-aware for recurring events)
    fireflies_cal_id: (
        str | None
    )  # iCalUID-derived (best-effort) to match Fireflies transcript cal_id
    account: str  # private|personal
    calendar_id: str  # primary
    event_id: str
    title: str
    start_local: datetime
    end_local: datetime
    html_link: str | None
    meet_link: str | None
    location: str | None
    description: str | None
    attendees: list[str]


def _get_token_path(account: str) -> Path:
    if account == "private":
        return TOKEN_PRIVATE_PATH
    if account == "personal":
        return TOKEN_PERSONAL_PATH
    raise ValueError(f"Unknown account: {account}")


def _load_credentials(account: str) -> Credentials:
    token_path = _get_token_path(account)
    creds: Credentials | None = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json(), encoding="utf-8")

    if not creds or not creds.valid:
        raise RuntimeError(
            f"Missing/invalid token for account '{account}'. "
            f"Run: .\\.venv\\Scripts\\python 90_System\\Skills\\gcal_today\\gcal_today.py auth --account {account}"
        )

    return creds


def auth_account(account: str) -> None:
    if account == "private":
        client_path = OAUTH_CLIENT_PRIVATE_PATH
    elif account == "personal":
        client_path = OAUTH_CLIENT_PERSONAL_PATH
    else:
        raise ValueError(f"Unknown account: {account}")

    if not client_path.exists():
        client_path = OAUTH_CLIENT_SHARED_PATH

    if not client_path.exists():
        raise RuntimeError(
            "Missing OAuth client file. Create one of:\n"
            f"- {OAUTH_CLIENT_PRIVATE_PATH}\n"
            f"- {OAUTH_CLIENT_PERSONAL_PATH}\n"
            f"- {OAUTH_CLIENT_SHARED_PATH}\n"
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(port=0)

    token_path = _get_token_path(account)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved token: {token_path}")


def _days_back_value(raw_value: int | None, default_days: int) -> int:
    if raw_value is None:
        return default_days
    if raw_value < 1:
        raise ValueError("--days-back must be >= 1")
    return raw_value


def _current_day_start_local() -> datetime:
    now = datetime.now().astimezone()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _upcoming_window_local(days_ahead: int = 14) -> tuple[datetime, datetime]:
    start = _current_day_start_local()
    # Inclusive calendar range (today + N days) implemented with exclusive end.
    end = start + timedelta(days=days_ahead + 1)
    return start, end


def _backfill_window_local(days_back: int) -> tuple[datetime, datetime]:
    end = _current_day_start_local() + timedelta(days=1)
    start = end - timedelta(days=days_back)
    return start, end


def _parse_dt(dt_str: str) -> datetime:
    # Google API returns RFC3339 with timezone offset; datetime.fromisoformat can parse it.
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone()


def _extract_meet_link(event: dict) -> str | None:
    conference = event.get("conferenceData") or {}
    entry_points = conference.get("entryPoints") or []
    for entry in entry_points:
        if entry.get("entryPointType") in ("video", "more"):
            uri = entry.get("uri")
            if uri:
                return uri
    uri = event.get("hangoutLink")
    if uri:
        return uri
    return None


def _extract_attendees(event: dict) -> list[str]:
    attendees = event.get("attendees") or []
    out: list[str] = []
    for a in attendees:
        email = a.get("email")
        if email:
            out.append(email)
    return sorted(set(out))


def _event_dedupe_key(event: dict) -> str | None:
    # For recurring events, iCalUID is shared by all occurrences, so include original start.
    event_id = event.get("id")
    iCalUID = event.get("iCalUID")
    original_start = (event.get("originalStartTime") or {}).get("dateTime") or (
        event.get("originalStartTime") or {}
    ).get("date")

    if iCalUID and original_start:
        return f"{iCalUID}__{original_start}"
    if event_id:
        return event_id
    if iCalUID:
        return iCalUID
    return None


def _fireflies_cal_id(event: dict) -> str | None:
    # Fireflies transcript `cal_id` often looks like: <base>_YYYYMMDDTHHMMSSZ
    # For Google Calendar events, approximate <base> from iCalUID by stripping instance markers and @google.com.
    iCalUID = (event.get("iCalUID") or "").strip()
    if not iCalUID:
        return None

    base = iCalUID.split("@", 1)[0]
    if "_R" in base:
        base = base.split("_R", 1)[0]
    base = base.strip()
    if not base:
        return None

    dt_str = (event.get("originalStartTime") or {}).get("dateTime") or (
        event.get("start") or {}
    ).get("dateTime")
    if not dt_str:
        return None

    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
    except Exception:
        return None

    stamp = dt.strftime("%Y%m%dT%H%M%SZ")
    return f"{base}_{stamp}"


def fetch_events_in_window(
    account: str,
    window_start: datetime,
    window_end: datetime,
    calendar_id: str = "primary",
) -> list[CalendarEvent]:
    creds = _load_credentials(account)
    service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=window_start.isoformat(),
            timeMax=window_end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            showDeleted=False,
        )
        .execute()
    )
    items = events_result.get("items", [])

    out: list[CalendarEvent] = []
    for ev in items:
        if ev.get("status") == "cancelled":
            continue
        start = ev.get("start") or {}
        end = ev.get("end") or {}
        start_dt = start.get("dateTime")
        end_dt = end.get("dateTime")
        if not start_dt or not end_dt:
            continue  # skip all-day events

        start_local = _parse_dt(start_dt)
        end_local = _parse_dt(end_dt)

        title = (ev.get("summary") or "").strip() or "(No title)"
        key = _event_dedupe_key(ev)
        if not key:
            continue

        out.append(
            CalendarEvent(
                key=key,
                fireflies_cal_id=_fireflies_cal_id(ev),
                account=account,
                calendar_id=calendar_id,
                event_id=ev.get("id") or "",
                title=title,
                start_local=start_local,
                end_local=end_local,
                html_link=ev.get("htmlLink"),
                meet_link=_extract_meet_link(ev),
                location=ev.get("location"),
                description=ev.get("description"),
                attendees=_extract_attendees(ev),
            )
        )
    return out


def fetch_upcoming_events(
    account: str, calendar_id: str = "primary", days_ahead: int = 14
) -> list[CalendarEvent]:
    window_start, window_end = _upcoming_window_local(days_ahead=days_ahead)
    return fetch_events_in_window(
        account, window_start, window_end, calendar_id=calendar_id
    )


def _sanitize_filename(text: str) -> str:
    text = text.strip()
    text = re.sub(r'[<>:"/\\\\|?*]+', "-", text)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "Untitled"
    # Keep it reasonably short for Windows paths
    return text[:120].rstrip()


def _yaml_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _strip_frontmatter(text: str) -> str:
    # Allow UTF-8 BOM / leading blank lines before YAML frontmatter.
    text = text.lstrip("\ufeff")
    return re.sub(r"(?s)^\s*---\r?\n.*?\r?\n---\r?\n*", "", text, count=1)


def _extract_preserved_tail(existing_text: str) -> str | None:
    match = re.search(r"(?ms)^##\s+Preparation\s*$.*\Z", existing_text)
    if not match:
        return None
    return existing_text[match.start() :]


def _default_manual_tail() -> str:
    return "## Preparation\n- ...\n\n## Meeting Notes\n- ...\n"


def _render_meeting_note(
    template_text: str, ev: CalendarEvent, preserved_tail: str | None = None
) -> str:
    date_str = ev.start_local.date().isoformat()
    start_str = ev.start_local.strftime("%H:%M")
    end_str = ev.end_local.strftime("%H:%M")

    rendered = template_text

    rendered = rendered.replace("date: YYYY-MM-DD", f"date: {date_str}")
    rendered = rendered.replace("start: HH:MM", f"start: {start_str}")
    rendered = rendered.replace("end: HH:MM", f"end: {end_str}")

    rendered = re.sub(
        r"^meeting_title:.*$",
        f"meeting_title: {_yaml_quote(ev.title)}",
        rendered,
        flags=re.M,
    )
    rendered = re.sub(r"^source:.*$", 'source: "google_calendar"', rendered, flags=re.M)

    attendees_block = ""
    if ev.attendees:
        attendees_block = "attendees:\n" + "".join(
            f"  - {_yaml_quote(a)}\n" for a in ev.attendees
        )
    else:
        attendees_block = 'attendees:\n  - ""\n'

    rendered = re.sub(
        r"(?ms)^attendees:\n(?:  -.*\n)*",
        attendees_block,
        rendered,
    )

    rendered = rendered.replace("{{meeting_title}}", ev.title)
    rendered = _strip_frontmatter(rendered).lstrip()
    # Remove template manual sections; we append a writable tail after auto metadata.
    rendered = re.sub(
        r"(?ms)\n##\s+(?:Preparation|Meeting\s+Notes|Notes)\s*\n.*$",
        "",
        rendered,
    ).rstrip()

    auto_lines: list[str] = []
    auto_lines.append("\n## Calendar (auto)\n")
    auto_lines.append(f"- Account: {ev.account}\n")
    auto_lines.append(f"- Calendar: {ev.calendar_id}\n")
    if ev.html_link:
        auto_lines.append(f"- Event: {ev.html_link}\n")
    if ev.meet_link:
        auto_lines.append(f"- Meet: {ev.meet_link}\n")
    if ev.location:
        auto_lines.append(f"- Location: {ev.location}\n")
    if ev.description:
        desc = ev.description.strip()
        if desc:
            auto_lines.append("\n### Description (auto)\n")
            auto_lines.append(desc)
            if not desc.endswith("\n"):
                auto_lines.append("\n")

    auto_lines.append(f"- UID: {ev.key}\n")
    if ev.fireflies_cal_id:
        auto_lines.append(f"- GCal cal_id: {ev.fireflies_cal_id}\n")
    auto_lines.append(
        f"- Synced: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
    )

    if preserved_tail is not None:
        out = rendered + "".join(auto_lines) + "\n" + preserved_tail
        if not out.endswith("\n"):
            out += "\n"
        return out

    return rendered + "".join(auto_lines) + "\n" + _default_manual_tail()


def _note_path_for_event(ev: CalendarEvent) -> tuple[Path, str]:
    year = ev.start_local.strftime("%Y")
    month = ev.start_local.strftime("%m")
    day = ev.start_local.strftime("%d")
    hhmm = ev.start_local.strftime("%H%M")
    title = _sanitize_filename(ev.title)
    folder = REPO_ROOT / "20_Meetings" / year / month / day
    filename = f"{hhmm} - {title}.md"
    return folder / filename, f"20_Meetings/{year}/{month}/{day}/{hhmm} - {title}"


def _month_key_for_event(ev: CalendarEvent) -> str:
    return ev.start_local.strftime("%Y-%m")


def _dedupe_events(
    private_events: list[CalendarEvent], personal_events: list[CalendarEvent]
) -> list[CalendarEvent]:
    chosen: dict[str, CalendarEvent] = {}
    for ev in private_events:
        chosen[ev.key] = ev
    for ev in personal_events:
        if ev.key not in chosen:
            chosen[ev.key] = ev
    return sorted(chosen.values(), key=lambda e: e.start_local)


def _insert_links_under_month(index_text: str, month_key: str, links: list[str]) -> str:
    header = f"## {month_key}"
    lines = index_text.splitlines(keepends=True)

    header_idx = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            header_idx = i
            break
    if header_idx is None:
        if not index_text.endswith("\n"):
            index_text += "\n"
        index_text += f"\n{header}\n"
        lines = index_text.splitlines(keepends=True)
        for i, line in enumerate(lines):
            if line.strip() == header:
                header_idx = i
                break

    assert header_idx is not None

    # Find insertion point: end of this month section (before next "## ")
    insert_at = len(lines)
    for j in range(header_idx + 1, len(lines)):
        if lines[j].startswith("## "):
            insert_at = j
            break

    existing = index_text
    new_lines: list[str] = []
    for link in links:
        bullet = f"- [[{link}]]\n"
        if bullet in existing:
            continue
        new_lines.append(bullet)

    if not new_lines:
        return index_text

    # Insert before insert_at, but after any existing bullets in this section.
    k = insert_at
    while k > header_idx + 1 and lines[k - 1].strip() == "":
        k -= 1
    lines[k:k] = new_lines
    return "".join(lines)


def _normalize_accounts(accounts: list[str] | None) -> list[str]:
    if not accounts:
        return ["private", "personal"]
    normalized: list[str] = []
    for account in accounts:
        if account not in {"private", "personal"}:
            raise ValueError(f"Unknown account: {account}")
        if account not in normalized:
            normalized.append(account)
    return normalized


def _sync_window(
    *,
    dry_run: bool,
    window_start: datetime,
    window_end: datetime,
    window_label: str,
    accounts: list[str] | None = None,
) -> None:
    template_text = MEETING_TEMPLATE_PATH.read_text(encoding="utf-8")
    accounts = _normalize_accounts(accounts)

    events_by_account: dict[str, list[CalendarEvent]] = {}
    for account in accounts:
        events_by_account[account] = fetch_events_in_window(
            account, window_start, window_end, "primary"
        )

    private_events = events_by_account.get("private", [])
    personal_events = events_by_account.get("personal", [])
    events = [
        ev for ev in _dedupe_events(private_events, personal_events) if ev.attendees
    ]

    created_paths: list[tuple[Path, str]] = []
    updated_paths: list[tuple[Path, str]] = []

    for ev in events:
        path, wiki_target = _note_path_for_event(ev)
        preserved_tail: str | None = None
        existed = path.exists()
        if existed:
            preserved_tail = _extract_preserved_tail(path.read_text(encoding="utf-8"))
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            content = _render_meeting_note(
                template_text, ev, preserved_tail=preserved_tail
            )
            path.write_text(content, encoding="utf-8")
        if existed:
            updated_paths.append((path, wiki_target))
        else:
            created_paths.append((path, wiki_target))

    links_by_month: dict[str, list[str]] = {}
    for ev in events:
        _, wiki_target = _note_path_for_event(ev)
        links_by_month.setdefault(_month_key_for_event(ev), []).append(wiki_target)

    if links_by_month:
        if not dry_run:
            index_text = MEETING_INDEX_PATH.read_text(encoding="utf-8")
            for month_key in sorted(links_by_month):
                links = sorted(set(links_by_month[month_key]))
                index_text = _insert_links_under_month(index_text, month_key, links)
            MEETING_INDEX_PATH.write_text(index_text, encoding="utf-8")

    print(f"Window: {window_label}")
    print(
        f"Events found: {len(events)} (private: {len(private_events)}, personal: {len(personal_events)})"
    )
    print(f"Created: {len(created_paths)}")
    for p, _ in created_paths:
        print(f"  + {p.relative_to(REPO_ROOT)}")
    print(f"Updated: {len(updated_paths)}")
    for p, _ in updated_paths[:20]:
        print(f"  ~ {p.relative_to(REPO_ROOT)}")
    if len(updated_paths) > 20:
        print("  ...")


def sync_today(
    dry_run: bool = False,
    days_ahead: int = 14,
    accounts: list[str] | None = None,
) -> None:
    window_start, window_end = _upcoming_window_local(days_ahead=days_ahead)
    _sync_window(
        dry_run=dry_run,
        window_start=window_start,
        window_end=window_end,
        window_label=f"today + {days_ahead} day(s)",
        accounts=accounts,
    )


def sync_days_back(
    dry_run: bool = False,
    days_back: int = 14,
    accounts: list[str] | None = None,
) -> None:
    window_start, window_end = _backfill_window_local(days_back=days_back)
    _sync_window(
        dry_run=dry_run,
        window_start=window_start,
        window_end=window_end,
        window_label=f"last {days_back} day(s)",
        accounts=accounts,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gcal_today")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("auth", help="Authenticate and store token for an account")
    p_auth.add_argument("--account", choices=["private", "personal"], required=True)

    p_sync = sub.add_parser(
        "sync",
        help="Sync upcoming meetings (default: today + 14 days) into meeting notes",
    )
    p_sync.add_argument("--dry-run", action="store_true")
    p_sync.add_argument(
        "--days-back",
        type=int,
        default=None,
        help="Backfill meetings from the last N days up to today",
    )
    p_sync.add_argument(
        "--accounts",
        nargs="+",
        choices=["private", "personal"],
        default=None,
        help="Only sync the selected Google Calendar accounts",
    )

    args = parser.parse_args(argv)

    if args.cmd == "auth":
        auth_account(args.account)
        return 0
    if args.cmd == "sync":
        if args.days_back is not None:
            days_back = _days_back_value(args.days_back, default_days=14)
            sync_days_back(
                dry_run=bool(args.dry_run),
                days_back=days_back,
                accounts=args.accounts,
            )
        else:
            sync_today(
                dry_run=bool(args.dry_run),
                days_ahead=14,
                accounts=args.accounts,
            )
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
