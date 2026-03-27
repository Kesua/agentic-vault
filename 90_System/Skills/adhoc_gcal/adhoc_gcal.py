from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


REPO_ROOT = Path(__file__).resolve().parents[3]
GCAL_SKILL_DIR = REPO_ROOT / "90_System" / "Skills" / "gcal_today"
if str(GCAL_SKILL_DIR) not in sys.path:
    sys.path.insert(0, str(GCAL_SKILL_DIR))

import gcal_today as gcal_base  # noqa: E402


SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
DRAFTS_DIR = REPO_ROOT / "70_Exports" / "gcal_drafts"
TOKEN_PRIVATE_PATH = gcal_base.SECRETS_DIR / "gcal_adhoc_token_private.json"
TOKEN_PERSONAL_PATH = gcal_base.SECRETS_DIR / "gcal_adhoc_token_personal.json"


def _get_token_path(account: str) -> Path:
    if account == "private":
        return TOKEN_PRIVATE_PATH
    if account == "personal":
        return TOKEN_PERSONAL_PATH
    raise ValueError(f"Unknown account: {account}")


def _get_client_path(account: str) -> Path:
    if account == "private" and gcal_base.OAUTH_CLIENT_PRIVATE_PATH.exists():
        return gcal_base.OAUTH_CLIENT_PRIVATE_PATH
    if account == "personal" and gcal_base.OAUTH_CLIENT_PERSONAL_PATH.exists():
        return gcal_base.OAUTH_CLIENT_PERSONAL_PATH
    if gcal_base.OAUTH_CLIENT_SHARED_PATH.exists():
        return gcal_base.OAUTH_CLIENT_SHARED_PATH
    raise RuntimeError(
        "Missing OAuth client file. Create one of:\n"
        f"- {gcal_base.OAUTH_CLIENT_PRIVATE_PATH}\n"
        f"- {gcal_base.OAUTH_CLIENT_PERSONAL_PATH}\n"
        f"- {gcal_base.OAUTH_CLIENT_SHARED_PATH}\n"
    )


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
            f"Run: .\\.venv\\Scripts\\python.exe 90_System\\Skills\\adhoc_gcal\\adhoc_gcal.py auth --account {account}"
        )
    return creds


def auth_account(account: str) -> None:
    client_path = _get_client_path(account)
    flow = InstalledAppFlow.from_client_secrets_file(str(client_path), SCOPES)
    creds = flow.run_local_server(port=0)
    token_path = _get_token_path(account)
    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(creds.to_json(), encoding="utf-8")
    print(f"Saved token: {token_path}")


def _service(account: str):
    return build(
        "calendar", "v3", credentials=_load_credentials(account), cache_discovery=False
    )


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _serialize_event(account: str, event: dict[str, Any]) -> dict[str, Any]:
    attendees = []
    for attendee in event.get("attendees") or []:
        email = attendee.get("email")
        if email:
            attendees.append(email)
    return {
        "account": account,
        "event_id": event.get("id"),
        "title": event.get("summary"),
        "start": (event.get("start") or {}).get("dateTime")
        or (event.get("start") or {}).get("date"),
        "end": (event.get("end") or {}).get("dateTime")
        or (event.get("end") or {}).get("date"),
        "attendees": attendees,
        "location": event.get("location"),
        "description": event.get("description"),
        "html_link": event.get("htmlLink"),
        "status": event.get("status"),
    }


def _iter_accounts(account: str) -> list[str]:
    if account == "both":
        return ["private", "personal"]
    return [account]


def command_list(args: argparse.Namespace) -> None:
    window_start, window_end = gcal_base._upcoming_window_local(days_ahead=args.days)
    events: list[dict[str, Any]] = []
    for account in _iter_accounts(args.account):
        service = _service(account)
        response = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=window_start.isoformat(),
                timeMax=window_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                showDeleted=False,
                maxResults=args.limit * 3,
            )
            .execute()
        )
        for event in response.get("items") or []:
            record = _serialize_event(account, event)
            if args.query:
                haystacks = [
                    record.get("title") or "",
                    record.get("description") or "",
                    record.get("location") or "",
                    " ".join(record.get("attendees") or []),
                ]
                if not any(
                    args.query.casefold() in str(text).casefold()
                    for text in haystacks
                    if text
                ):
                    continue
            events.append(record)
    events.sort(key=lambda item: str(item.get("start") or ""))
    print(
        json.dumps(
            {"count": len(events), "events": events[: args.limit]},
            ensure_ascii=False,
            indent=2,
        )
    )


def command_show(args: argparse.Namespace) -> None:
    for account in _iter_accounts(args.account):
        service = _service(account)
        try:
            event = (
                service.events()
                .get(calendarId="primary", eventId=args.event_id)
                .execute()
            )
        except Exception:
            continue
        print(
            json.dumps(_serialize_event(account, event), ensure_ascii=False, indent=2)
        )
        return
    raise RuntimeError(
        f"Event '{args.event_id}' not found for account setting '{args.account}'"
    )


def _draft_filename(title: str) -> str:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    safe_title = re.sub(r'[<>:"/\\\\|?*]+', "-", title).strip() or "Untitled"
    safe_title = _normalize_text(safe_title)[:80].rstrip()
    return f"{stamp} - {safe_title}.md"


def _quote_yaml(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _draft_text(payload: dict[str, Any]) -> str:
    attendees = payload.get("attendees") or []
    attendee_lines = (
        "\n".join(f"  - {email}" for email in attendees) if attendees else "  -"
    )
    body_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return (
        "---\n"
        "type: gcal_meeting_draft\n"
        "status: pending_confirmation\n"
        f"account: {payload['account']}\n"
        f"title: {_quote_yaml(payload['title'])}\n"
        f"start: {_quote_yaml(payload['start'])}\n"
        f"end: {_quote_yaml(payload['end'])}\n"
        "attendees:\n"
        f"{attendee_lines}\n"
        "---\n\n"
        "# Google Calendar Draft\n\n"
        "- Review the payload below.\n"
        "- Confirm with `confirm-draft-create --draft <path>` when ready.\n"
        "- Edit the payload block only if you know the field shape.\n\n"
        "## Payload\n\n"
        "```json\n"
        f"{body_json}\n"
        "```\n"
    )


def _build_event_payload(args: argparse.Namespace) -> dict[str, Any]:
    start = datetime.fromisoformat(args.start)
    if args.end:
        end = datetime.fromisoformat(args.end)
    else:
        end = start + timedelta(minutes=args.duration_minutes)
    if end <= start:
        raise RuntimeError("Event end must be after start")
    return {
        "account": args.account,
        "title": args.title,
        "start": start.astimezone().isoformat(),
        "end": end.astimezone().isoformat(),
        "attendees": args.attendee or [],
        "location": args.location,
        "description": args.description,
    }


def command_create_draft(args: argparse.Namespace) -> None:
    payload = _build_event_payload(args)
    DRAFTS_DIR.mkdir(parents=True, exist_ok=True)
    path = DRAFTS_DIR / _draft_filename(payload["title"])
    path.write_text(_draft_text(payload), encoding="utf-8")
    print(
        json.dumps(
            {"draft": str(path), "payload": payload}, ensure_ascii=False, indent=2
        )
    )


def _load_draft_payload(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\s*(.*?)```", text, flags=re.S)
    if not match:
        raise RuntimeError(f"Could not find JSON payload block in {path}")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise RuntimeError(f"Invalid draft payload in {path}")
    return payload


def _mark_draft_created(path: Path, event: dict[str, Any]) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace("status: pending_confirmation", "status: created", 1)
    text = text.rstrip() + (
        "\n\n## Created Event\n\n"
        f"- Event ID: {event.get('id')}\n"
        f"- Link: {event.get('htmlLink')}\n"
        f"- Created: {datetime.now().astimezone().isoformat(timespec='seconds')}\n"
    )
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def command_confirm_draft(args: argparse.Namespace) -> None:
    draft_path = Path(args.draft)
    payload = _load_draft_payload(draft_path)
    account = str(payload.get("account") or "")
    if account not in {"private", "personal"}:
        raise RuntimeError(f"Draft {draft_path} is missing a valid account")
    service = _service(account)
    body: dict[str, Any] = {
        "summary": payload.get("title"),
        "start": {"dateTime": payload.get("start")},
        "end": {"dateTime": payload.get("end")},
    }
    attendees = payload.get("attendees") or []
    if attendees:
        body["attendees"] = [{"email": email} for email in attendees]
    if payload.get("location"):
        body["location"] = payload["location"]
    if payload.get("description"):
        body["description"] = payload["description"]
    event = service.events().insert(calendarId="primary", body=body).execute()
    _mark_draft_created(draft_path, event)
    print(json.dumps(_serialize_event(account, event), ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="adhoc_gcal",
        description="Ad-hoc Google Calendar assistant: inspect meetings and create confirmed draft-based events.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser(
        "auth", help="Authenticate and store an ad-hoc Calendar token"
    )
    p_auth.add_argument("--account", choices=["private", "personal"], required=True)
    p_auth.set_defaults(func=lambda args: auth_account(args.account))

    p_list = sub.add_parser("list", help="List upcoming meetings")
    p_list.add_argument(
        "--account", choices=["private", "personal", "both"], default="both"
    )
    p_list.add_argument("--days", type=int, default=14)
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--query")
    p_list.set_defaults(func=command_list)

    p_show = sub.add_parser("show", help="Show one event by Google Calendar event ID")
    p_show.add_argument(
        "--account", choices=["private", "personal", "both"], default="both"
    )
    p_show.add_argument("--event-id", required=True)
    p_show.set_defaults(func=command_show)

    p_draft = sub.add_parser(
        "create-meeting-draft",
        help="Create a local draft note for a new calendar event",
    )
    p_draft.add_argument("--account", choices=["private", "personal"], required=True)
    p_draft.add_argument("--title", required=True)
    p_draft.add_argument(
        "--start", required=True, help="ISO datetime with timezone offset"
    )
    p_draft.add_argument("--end", help="ISO datetime with timezone offset")
    p_draft.add_argument("--duration-minutes", type=int, default=30)
    p_draft.add_argument("--attendee", action="append")
    p_draft.add_argument("--location")
    p_draft.add_argument("--description")
    p_draft.set_defaults(func=command_create_draft)

    p_confirm = sub.add_parser(
        "confirm-draft-create",
        help="Create the calendar event from a pending local draft note",
    )
    p_confirm.add_argument("--draft", required=True)
    p_confirm.set_defaults(func=command_confirm_draft)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
