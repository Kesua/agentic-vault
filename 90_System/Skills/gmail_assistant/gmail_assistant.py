from __future__ import annotations

import argparse
import base64
import email.utils
import html
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
OAUTH_CLIENT_PRIVATE_PATH = SECRETS_DIR / "gmail_oauth_client_private.json"
OAUTH_CLIENT_PERSONAL_PATH = SECRETS_DIR / "gmail_oauth_client_personal.json"
OAUTH_CLIENT_SHARED_PATH = SECRETS_DIR / "gmail_oauth_client.json"
TOKEN_PRIVATE_PATH = SECRETS_DIR / "gmail_token_private.json"
TOKEN_PERSONAL_PATH = SECRETS_DIR / "gmail_token_personal.json"

INBOX_PATH = REPO_ROOT / "00_Mailbox" / "_Mailbox.md"
DAILY_BRIEFS_ROOT = REPO_ROOT / "10_DailyBriefs"
PEOPLE_DIR = REPO_ROOT / "40_People"
PEOPLE_INDEX_PATH = PEOPLE_DIR / "_PeopleIndex.md"
CREATE_LINKS_PATH = (
    REPO_ROOT / "90_System" / "Skills" / "create_links" / "create_links.py"
)

GMAIL_DAILY_BRIEF_HEADING = "# Gmail"
PEOPLE_INDEX_AUTO_HEADING = "## Gmail Contacts (auto)"


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
class GmailMessage:
    id: str
    thread_id: str
    label_ids: tuple[str, ...]
    internal_ts: int
    subject: str
    from_name: str
    from_email: str
    to_emails: tuple[str, ...]
    cc_emails: tuple[str, ...]
    reply_to_emails: tuple[str, ...]
    date_header: str
    snippet: str
    body_text: str
    body_html: str
    is_draft: bool
    attachments: tuple["GmailAttachment", ...]


@dataclass(frozen=True)
class GmailAttachment:
    attachment_id: str
    filename: str
    mime_type: str
    size: int


@dataclass(frozen=True)
class GmailThreadSummary:
    thread_id: str
    subject: str
    last_at: datetime
    participants: tuple[str, ...]
    message_count: int
    unread: bool
    inbox: bool
    latest_from: str
    latest_from_email: str
    snippet: str


@dataclass(frozen=True)
class ContactCandidate:
    name: str
    emails: tuple[str, ...]
    aliases: tuple[str, ...]
    last_touch: str


class _HTMLToTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "tr"}:
            self.parts.append("\n")

    def get_text(self) -> str:
        text = "".join(self.parts)
        text = html.unescape(text)
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()


def _get_token_path(account: str) -> Path:
    if account == "private":
        return TOKEN_PRIVATE_PATH
    if account == "personal":
        return TOKEN_PERSONAL_PATH
    raise ValueError(f"Unknown account: {account}")


def _get_client_path(account: str) -> Path:
    if account == "private":
        preferred = OAUTH_CLIENT_PRIVATE_PATH
    elif account == "personal":
        preferred = OAUTH_CLIENT_PERSONAL_PATH
    else:
        raise ValueError(f"Unknown account: {account}")
    return preferred if preferred.exists() else OAUTH_CLIENT_SHARED_PATH


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
            f"Run: .\\.venv\\Scripts\\python.exe 90_System\\Skills\\gmail_assistant\\gmail_assistant.py auth --account {account}"
        )

    return creds


def auth_account(account: str) -> None:
    client_path = _get_client_path(account)
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


def _gmail_service(account: str):
    creds = _load_credentials(account)
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _safe_execute(request: Any) -> dict[str, Any]:
    try:
        return request.execute()
    except HttpError as exc:
        detail = exc.reason or str(exc)
        raise RuntimeError(f"Gmail API request failed: {detail}") from exc


def _get_profile_email(service: Any) -> str:
    profile = _safe_execute(service.users().getProfile(userId="me"))
    value = str(profile.get("emailAddress") or "").strip().casefold()
    if not value:
        raise RuntimeError(
            "Unable to determine authorized Gmail address for the selected account"
        )
    return value


def _gmail_list_threads(service: Any, query: str, max_results: int = 20) -> list[str]:
    token: str | None = None
    out: list[str] = []
    while True:
        payload = _safe_execute(
            service.users()
            .threads()
            .list(
                userId="me", q=query, maxResults=min(max_results, 100), pageToken=token
            )
        )
        for item in payload.get("threads", []) or []:
            thread_id = str(item.get("id") or "").strip()
            if thread_id:
                out.append(thread_id)
                if len(out) >= max_results:
                    return out
        token = payload.get("nextPageToken")
        if not token:
            break
    return out


def _header_map(headers: list[dict[str, Any]] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for header in headers or []:
        name = str(header.get("name") or "").strip().casefold()
        value = str(header.get("value") or "").strip()
        if name and value and name not in out:
            out[name] = value
    return out


def _decode_body(data: str | None) -> str:
    if not data:
        return ""
    padded = data + "=" * (-len(data) % 4)
    try:
        decoded = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception:
        return ""
    return decoded.decode("utf-8", errors="replace").strip()


def _collect_bodies(
    part: dict[str, Any], plain_parts: list[str], html_parts: list[str]
) -> None:
    mime_type = str(part.get("mimeType") or "").strip().lower()
    body = part.get("body") or {}
    data = body.get("data")

    if mime_type == "text/plain":
        text = _decode_body(data)
        if text:
            plain_parts.append(text)
    elif mime_type == "text/html":
        text = _decode_body(data)
        if text:
            html_parts.append(text)

    for child in part.get("parts", []) or []:
        if isinstance(child, dict):
            _collect_bodies(child, plain_parts, html_parts)


def _collect_attachments(part: dict[str, Any], out: list[GmailAttachment]) -> None:
    mime_type = str(part.get("mimeType") or "").strip()
    filename = str(part.get("filename") or "").strip()
    body = part.get("body") or {}
    attachment_id = str(body.get("attachmentId") or "").strip()
    size = int(body.get("size") or 0)

    if filename and attachment_id:
        out.append(
            GmailAttachment(
                attachment_id=attachment_id,
                filename=filename,
                mime_type=mime_type,
                size=size,
            )
        )

    for child in part.get("parts", []) or []:
        if isinstance(child, dict):
            _collect_attachments(child, out)


def _html_to_text(value: str) -> str:
    parser = _HTMLToTextParser()
    parser.feed(value)
    parser.close()
    return parser.get_text()


def _parse_address_list(raw_value: str) -> tuple[str, ...]:
    emails: list[str] = []
    for _, email_addr in email.utils.getaddresses([raw_value]):
        normalized = email_addr.strip().casefold()
        if normalized:
            emails.append(normalized)
    return tuple(_dedupe_preserve_order(emails))


def _normalize_message(raw: dict[str, Any]) -> GmailMessage:
    payload = raw.get("payload") or {}
    headers = _header_map(payload.get("headers"))
    plain_parts: list[str] = []
    html_parts: list[str] = []
    attachments: list[GmailAttachment] = []
    _collect_bodies(payload, plain_parts, html_parts)
    _collect_attachments(payload, attachments)

    body_text = "\n\n".join(part for part in plain_parts if part).strip()
    body_html = "\n\n".join(part for part in html_parts if part).strip()
    if not body_text and body_html:
        body_text = _html_to_text(body_html)

    from_name, from_email = email.utils.parseaddr(headers.get("from", ""))
    return GmailMessage(
        id=str(raw.get("id") or ""),
        thread_id=str(raw.get("threadId") or ""),
        label_ids=tuple(str(x) for x in (raw.get("labelIds") or []) if str(x).strip()),
        internal_ts=int(raw.get("internalDate") or 0),
        subject=headers.get("subject", "").strip() or "(No subject)",
        from_name=from_name.strip(),
        from_email=from_email.strip().casefold(),
        to_emails=_parse_address_list(headers.get("to", "")),
        cc_emails=_parse_address_list(headers.get("cc", "")),
        reply_to_emails=_parse_address_list(headers.get("reply-to", "")),
        date_header=headers.get("date", "").strip(),
        snippet=str(raw.get("snippet") or "").strip(),
        body_text=body_text,
        body_html=body_html,
        is_draft="DRAFT" in (raw.get("labelIds") or []),
        attachments=tuple(attachments),
    )


def _get_thread_messages(service: Any, thread_id: str) -> list[GmailMessage]:
    payload = _safe_execute(
        service.users().threads().get(userId="me", id=thread_id, format="full")
    )
    messages = [
        _normalize_message(item)
        for item in payload.get("messages", []) or []
        if isinstance(item, dict)
    ]
    return sorted(messages, key=lambda msg: (msg.internal_ts, msg.id))


def _clip_text(value: str, limit: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


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


def _message_datetime(message: GmailMessage) -> datetime:
    return datetime.fromtimestamp(message.internal_ts / 1000).astimezone()


def _thread_summary(messages: list[GmailMessage]) -> GmailThreadSummary | None:
    if not messages:
        return None
    latest = messages[-1]
    label_set = {label for message in messages for label in message.label_ids}
    participants = _dedupe_preserve_order(
        [msg.from_email for msg in messages if msg.from_email]
        + [email_addr for msg in messages for email_addr in msg.to_emails]
    )
    return GmailThreadSummary(
        thread_id=latest.thread_id,
        subject=latest.subject,
        last_at=_message_datetime(latest),
        participants=tuple(participants),
        message_count=len(messages),
        unread="UNREAD" in label_set,
        inbox="INBOX" in label_set,
        latest_from=latest.from_name or latest.from_email,
        latest_from_email=latest.from_email,
        snippet=latest.snippet or _clip_text(latest.body_text, 180),
    )


def _search_threads(
    account: str, query: str, max_results: int
) -> list[GmailThreadSummary]:
    service = _gmail_service(account)
    thread_ids = _gmail_list_threads(service, query, max_results=max_results)
    summaries: list[GmailThreadSummary] = []
    for thread_id in thread_ids:
        summary = _thread_summary(_get_thread_messages(service, thread_id))
        if summary:
            summaries.append(summary)
    return sorted(summaries, key=lambda item: item.last_at, reverse=True)


def command_search(args: argparse.Namespace) -> None:
    results = _search_threads(args.account, args.query, args.max_results)
    for item in results:
        print(
            f"{item.last_at.isoformat(timespec='minutes')} | {item.thread_id} | "
            f"{item.subject} | from {item.latest_from} | {item.snippet}"
        )
    print(f"Threads found: {len(results)}")


def _summarize_messages(messages: list[GmailMessage], my_email: str) -> str:
    lines: list[str] = []
    for message in messages:
        author = (
            "me"
            if message.from_email == my_email
            else (message.from_name or message.from_email or "unknown")
        )
        when = _message_datetime(message).isoformat(timespec="minutes")
        snippet = _clip_text(message.body_text or message.snippet, 240)
        lines.append(f"- {when} | {author}: {snippet}")
    return "\n".join(lines)


def _thread_header(subject: str, messages: list[GmailMessage]) -> list[str]:
    participants = _dedupe_preserve_order(
        [msg.from_email for msg in messages if msg.from_email]
        + [email_addr for msg in messages for email_addr in msg.to_emails]
    )
    started = _message_datetime(messages[0]).isoformat(timespec="minutes")
    last = _message_datetime(messages[-1]).isoformat(timespec="minutes")
    return [
        f"Subject: {subject}",
        f"Messages: {len(messages)}",
        f"Attachments: {sum(len(message.attachments) for message in messages)}",
        f"Started: {started}",
        f"Last message: {last}",
        f"Participants: {', '.join(participants) if participants else '(unknown)'}",
        "",
    ]


def _sanitize_path_component(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', "-", value.strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip().rstrip(".")
    return cleaned or "attachment"


def _attachment_output_dir(
    messages: list[GmailMessage], thread_id: str, explicit_dir: str | None
) -> Path:
    if explicit_dir:
        path = Path(explicit_dir)
        return path if path.is_absolute() else (REPO_ROOT / path)
    thread_day = _message_datetime(messages[-1]).date()
    return (
        REPO_ROOT
        / "00_Mailbox"
        / thread_day.strftime("%Y")
        / thread_day.strftime("%m")
        / thread_day.strftime("%d")
        / "attachments"
        / thread_id
    )


def _download_attachment(
    service: Any, message_id: str, attachment: GmailAttachment
) -> bytes:
    payload = _safe_execute(
        service.users()
        .messages()
        .attachments()
        .get(
            userId="me",
            messageId=message_id,
            id=attachment.attachment_id,
        )
    )
    data = str(payload.get("data") or "")
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def _replace_or_append_section(text: str, heading: str, lines: list[str]) -> str:
    normalized = text.rstrip()
    if normalized:
        normalized += "\n"
    body = heading + "\n\n" + "\n".join(lines).rstrip() + "\n"
    pattern = re.compile(rf"(?ms)^{re.escape(heading)}\n.*?(?=^#{{1,6}} |\Z)")
    if pattern.search(normalized):
        return pattern.sub(body, normalized, count=1)
    if normalized and not normalized.endswith("\n\n"):
        normalized += "\n"
    return normalized + body


def _extract_section(text: str, heading: str) -> list[str]:
    pattern = re.compile(rf"(?ms)^{re.escape(heading)}\n(.*?)(?=^#{{1,6}} |\Z)")
    match = pattern.search(text)
    if not match:
        return []
    lines = [line.rstrip() for line in match.group(1).strip().splitlines()]
    return [line for line in lines if line.strip()]


def _merge_bullets(existing_lines: list[str], new_lines: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in [*existing_lines, *new_lines]:
        normalized = line.strip()
        key = normalized.casefold()
        if not normalized or key in seen:
            continue
        seen.add(key)
        out.append(normalized)
    return out


def _ensure_daily_brief_path(for_day: date) -> Path:
    path = (
        DAILY_BRIEFS_ROOT
        / for_day.strftime("%Y")
        / for_day.strftime("%m")
        / f"{for_day.isoformat()}_Daily_Brief.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_to_daily_brief(lines: list[str]) -> None:
    if not lines:
        return
    path = _ensure_daily_brief_path(datetime.now().astimezone().date())
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing_section = _extract_section(existing, GMAIL_DAILY_BRIEF_HEADING)
    merged = _merge_bullets(existing_section, lines)
    updated = _replace_or_append_section(existing, GMAIL_DAILY_BRIEF_HEADING, merged)
    path.write_text(updated, encoding="utf-8")
    print(f"Updated Daily Brief: {path}")


def _append_to_inbox(lines: list[str]) -> None:
    if not lines:
        return
    text = INBOX_PATH.read_text(encoding="utf-8")
    marker = "## Capture (paste new items at the top)\n"
    idx = text.find(marker)
    if idx < 0:
        raise RuntimeError(f"Could not find inbox capture section in {INBOX_PATH}")
    start = idx + len(marker)
    insertion = "\n".join(lines) + "\n"
    updated = text[:start] + insertion + text[start:]
    INBOX_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated Inbox: {INBOX_PATH}")


def _strip_frontmatter(text: str) -> str:
    return re.sub(r"(?s)^\ufeff?---\r?\n.*?\r?\n---\r?\n*", "", text, count=1)


def _parse_frontmatter(text: str) -> dict[str, object]:
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
        if raw_value:
            data[key] = _yaml_unquote(raw_value)
        else:
            data[key] = []
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


def _ensure_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _sanitize_filename(text: str) -> str:
    text = re.sub(r'[<>:"/\\\\|?*]+', "-", text.strip())
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return text[:120] if text else "Unknown Person"


def _slug_aliases_from_email(email_addr: str) -> list[str]:
    local = email_addr.split("@", 1)[0].strip().split("+", 1)[0]
    if not local:
        return []
    return [local]


def _best_contact_name(raw_name: str, email_addr: str) -> str:
    cleaned = " ".join(part for part in raw_name.strip().split())
    if cleaned:
        return cleaned
    local = email_addr.split("@", 1)[0].split("+", 1)[0]
    tokens = [token for token in re.split(r"[._-]+", local) if token]
    if not tokens:
        return email_addr
    return " ".join(token[:1].upper() + token[1:] for token in tokens)


def _extract_contacts_from_messages(
    messages: list[GmailMessage], my_email: str
) -> list[ContactCandidate]:
    by_email: dict[str, dict[str, str]] = {}
    for message in messages:
        message_day = _message_datetime(message).date().isoformat()
        if message.from_email and message.from_email != my_email:
            name = _best_contact_name(message.from_name, message.from_email)
            entry = by_email.setdefault(
                message.from_email, {"name": name, "last_touch": message_day}
            )
            if len(name) > len(entry["name"]):
                entry["name"] = name
            entry["last_touch"] = max(entry["last_touch"], message_day)
        for email_addr in [*message.to_emails, *message.cc_emails]:
            if email_addr and email_addr != my_email:
                name = _best_contact_name("", email_addr)
                entry = by_email.setdefault(
                    email_addr, {"name": name, "last_touch": message_day}
                )
                entry["last_touch"] = max(entry["last_touch"], message_day)

    out: list[ContactCandidate] = []
    for email_addr, payload in sorted(by_email.items()):
        name = payload["name"].strip()
        aliases = _dedupe_preserve_order(
            [name, email_addr, *_slug_aliases_from_email(email_addr)]
        )
        out.append(
            ContactCandidate(
                name=name,
                emails=(email_addr,),
                aliases=tuple(aliases),
                last_touch=payload["last_touch"],
            )
        )
    return out


def _load_people_lookup() -> tuple[dict[str, Path], dict[str, Path]]:
    by_email: dict[str, Path] = {}
    by_alias: dict[str, Path] = {}
    for path in sorted(PEOPLE_DIR.glob("*.md")):
        if path == PEOPLE_INDEX_PATH or path.name.startswith("_"):
            continue
        metadata = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if str(metadata.get("type", "")).strip() != "person":
            continue
        for email_addr in _ensure_list(metadata.get("emails")):
            by_email[email_addr.casefold()] = path
        aliases = _ensure_list(metadata.get("aliases"))
        aliases.append(path.stem)
        for alias in aliases:
            by_alias[alias.casefold()] = path
    return by_email, by_alias


def _find_person_note(
    contact: ContactCandidate, by_email: dict[str, Path], by_alias: dict[str, Path]
) -> Path | None:
    for email_addr in contact.emails:
        if email_addr.casefold() in by_email:
            return by_email[email_addr.casefold()]
    for alias in contact.aliases:
        if alias.casefold() in by_alias:
            return by_alias[alias.casefold()]
    return None


def _render_person_note(metadata: dict[str, object], body: str, title: str) -> str:
    aliases = _ensure_list(metadata.get("aliases"))
    emails = _ensure_list(metadata.get("emails"))
    org = str(metadata.get("org", "") or "")
    role = str(metadata.get("role", "") or "")
    team = str(metadata.get("team", "") or "")
    timezone_value = str(metadata.get("timezone", "") or "")
    last_touch = str(metadata.get("last_touch", "") or "")

    lines = ["---", "type: person", "aliases:"]
    for alias in aliases:
        lines.append(f"  - {_yaml_quote(alias)}")
    lines.append("emails:")
    for email_addr in emails:
        lines.append(f"  - {_yaml_quote(email_addr)}")
    lines.extend(
        [
            f"org: {_yaml_quote(org)}",
            f"role: {_yaml_quote(role)}",
            f"team: {_yaml_quote(team)}",
            f"timezone: {_yaml_quote(timezone_value)}",
            f"last_touch: {_yaml_quote(last_touch)}",
            "---",
            "",
        ]
    )

    clean_body = _strip_frontmatter(body).lstrip("\ufeff")
    if clean_body.strip():
        return "\n".join(lines) + clean_body.lstrip()

    return "\n".join(lines) + (
        f"# {title}\n\n"
        "## Quick facts\n"
        f"- Org: {org}\n"
        f"- Role: {role}\n"
        f"- Team: {team}\n"
        f"- Timezone: {timezone_value}\n"
        f"- Last touch: {last_touch}\n\n"
        "## Notes\n"
        "- Email contact discovered via Gmail sync\n"
    )


def _update_people_index(
    contacts: list[ContactCandidate], dry_run: bool = False
) -> None:
    if not PEOPLE_INDEX_PATH.exists():
        return
    existing = PEOPLE_INDEX_PATH.read_text(encoding="utf-8")
    by_email, by_alias = _load_people_lookup()
    lines: list[str] = []
    for contact in contacts:
        if not contact.emails:
            continue
        note_path = _find_person_note(contact, by_email, by_alias)
        label = note_path.stem if note_path else _sanitize_filename(contact.name)
        lines.append(
            f"- [[{label}]] ({contact.emails[0]}, last touch: {contact.last_touch})"
        )
    updated = _replace_or_append_section(existing, PEOPLE_INDEX_AUTO_HEADING, lines)
    if dry_run:
        print(f"Would update People Index: {PEOPLE_INDEX_PATH}")
        return
    PEOPLE_INDEX_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated People Index: {PEOPLE_INDEX_PATH}")


def _run_create_links() -> None:
    if not CREATE_LINKS_PATH.exists():
        return
    subprocess.run(
        [sys.executable, str(CREATE_LINKS_PATH), "sync"], cwd=str(REPO_ROOT), check=True
    )


def _sync_contacts(contacts: list[ContactCandidate], dry_run: bool = False) -> None:
    if not contacts:
        return
    by_email, by_alias = _load_people_lookup()
    updated_any = False
    for contact in contacts:
        note_path = _find_person_note(contact, by_email, by_alias)
        if note_path is None:
            note_path = PEOPLE_DIR / f"{_sanitize_filename(contact.name)}.md"
            metadata: dict[str, object] = {"type": "person"}
            body = ""
        else:
            text = note_path.read_text(encoding="utf-8")
            metadata = _parse_frontmatter(text)
            body = text

        aliases = _dedupe_preserve_order(
            [*_ensure_list(metadata.get("aliases")), *contact.aliases, contact.name]
        )
        emails = _dedupe_preserve_order(
            [*_ensure_list(metadata.get("emails")), *contact.emails]
        )
        metadata["aliases"] = aliases
        metadata["emails"] = emails
        metadata["last_touch"] = max(
            str(metadata.get("last_touch", "") or ""), contact.last_touch
        )
        rendered = _render_person_note(metadata, body, title=contact.name)

        if dry_run:
            print(f"Would update person note: {note_path}")
        else:
            note_path.write_text(rendered, encoding="utf-8")
            print(f"Updated person note: {note_path}")
            updated_any = True

    _update_people_index(contacts, dry_run=dry_run)
    if updated_any and not dry_run:
        _run_create_links()


def command_summarize_thread(args: argparse.Namespace) -> None:
    service = _gmail_service(args.account)
    my_email = _get_profile_email(service)
    messages = _get_thread_messages(service, args.thread_id)
    if not messages:
        raise RuntimeError(f"Thread not found or empty: {args.thread_id}")

    summary_lines = _thread_header(messages[-1].subject, messages)
    summary_lines.append(_summarize_messages(messages, my_email))
    text = "\n".join(summary_lines)
    print(text)

    if args.dry_run:
        if args.to_inbox:
            print(f"Would append summary signal to Inbox: {messages[-1].subject}")
        if args.to_daily_brief:
            print(f"Would append summary signal to Daily Brief: {messages[-1].subject}")
        return

    if args.to_inbox:
        _append_to_inbox(
            [
                f"`{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}` - Gmail thread summary: {messages[-1].subject} ({args.thread_id})"
            ]
        )
    if args.to_daily_brief:
        _append_to_daily_brief(
            [
                f"- Thread: {messages[-1].subject} (`{args.thread_id}`)",
                f"- Summary generated: {datetime.now().astimezone().isoformat(timespec='minutes')}",
            ]
        )


def command_download_attachments(args: argparse.Namespace) -> None:
    service = _gmail_service(args.account)
    messages = _get_thread_messages(service, args.thread_id)
    if not messages:
        raise RuntimeError(f"Thread not found or empty: {args.thread_id}")

    output_dir = args.output_dir or None
    target_dir = _attachment_output_dir(messages, args.thread_id, output_dir)
    written = 0
    seen_names: dict[str, int] = {}

    for message in messages:
        for attachment in message.attachments:
            base_name = _sanitize_path_component(attachment.filename)
            seen_count = seen_names.get(base_name.casefold(), 0)
            seen_names[base_name.casefold()] = seen_count + 1
            if seen_count:
                stem = Path(base_name).stem
                ext = Path(base_name).suffix
                file_name = f"{stem}_{seen_count + 1}{ext}"
            else:
                file_name = base_name
            destination = target_dir / file_name

            if args.dry_run:
                print(
                    f"Would save: {destination} ({attachment.mime_type}, {attachment.size} bytes)"
                )
                written += 1
                continue

            target_dir.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(
                _download_attachment(service, message.id, attachment)
            )
            print(
                f"Saved: {destination} ({attachment.mime_type}, {attachment.size} bytes)"
            )
            written += 1

    if written == 0:
        print("No attachments found in thread.")
        return
    print(f"Attachments processed: {written}")


def _today_query() -> str:
    today = datetime.now().astimezone().date()
    tomorrow = today + timedelta(days=1)
    return f"after:{today.isoformat()} before:{tomorrow.isoformat()}"


def command_list_today(args: argparse.Namespace) -> None:
    results = _search_threads(args.account, _today_query(), args.max_results)
    for item in results:
        print(
            f"{item.last_at.isoformat(timespec='minutes')} | {item.subject} | {item.latest_from} | {item.snippet}"
        )
    print(f"Threads found today: {len(results)}")


def _find_unanswered_threads(
    account: str, max_results: int
) -> list[GmailThreadSummary]:
    service = _gmail_service(account)
    my_email = _get_profile_email(service)
    thread_ids = _gmail_list_threads(service, "in:inbox", max_results=max_results * 3)
    out: list[GmailThreadSummary] = []
    for thread_id in thread_ids:
        messages = _get_thread_messages(service, thread_id)
        non_drafts = [msg for msg in messages if not msg.is_draft]
        if not non_drafts:
            continue
        latest = non_drafts[-1]
        if latest.from_email == my_email:
            continue
        summary = _thread_summary(messages)
        if not summary or not summary.inbox:
            continue
        out.append(summary)
        if len(out) >= max_results:
            break
    return sorted(out, key=lambda item: item.last_at, reverse=True)


def command_list_unanswered(args: argparse.Namespace) -> None:
    results = _find_unanswered_threads(args.account, args.max_results)
    for item in results:
        print(
            f"{item.last_at.isoformat(timespec='minutes')} | {item.thread_id} | "
            f"{item.subject} | waiting on reply to {item.latest_from} | {item.snippet}"
        )
    print(f"Unanswered Inbox threads: {len(results)}")

    if args.to_inbox:
        lines = [
            f"`{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}` - Email follow-up: {item.subject} ({item.latest_from})"
            for item in results
        ]
        _append_to_inbox(lines)
    if args.to_daily_brief:
        lines = [
            f"- Follow up: {item.subject} ({item.latest_from})" for item in results
        ]
        _append_to_daily_brief(lines)


def _resolve_person_query(person_query: str) -> set[str]:
    raw = person_query.strip()
    if not raw:
        return set()
    candidates = {raw.casefold()}

    note_path = PEOPLE_DIR / f"{raw}.md"
    if not note_path.exists():
        return candidates

    metadata = _parse_frontmatter(note_path.read_text(encoding="utf-8"))
    emails = {
        str(item).strip().casefold()
        for item in _ensure_list(metadata.get("emails"))
        if str(item).strip()
    }
    aliases = {
        str(item).strip().casefold()
        for item in _ensure_list(metadata.get("aliases"))
        if str(item).strip()
    }
    aliases.add(raw.casefold())
    return emails | aliases


def command_list_by_person(args: argparse.Namespace) -> None:
    candidates = _resolve_person_query(args.person)
    email_query = " OR ".join(
        f'"{value}"' for value in sorted(candidates) if "@" in value
    )
    query = email_query or args.person
    results = _search_threads(args.account, query, args.max_results)
    filtered: list[GmailThreadSummary] = []
    for item in results:
        haystack = " ".join(
            [
                item.latest_from_email,
                item.latest_from,
                item.subject,
                " ".join(item.participants),
            ]
        ).casefold()
        if any(candidate in haystack for candidate in candidates):
            filtered.append(item)
    for item in filtered:
        print(
            f"{item.last_at.isoformat(timespec='minutes')} | {item.subject} | {item.latest_from} | {item.thread_id}"
        )
    print(f"Threads matched: {len(filtered)}")


def _draft_message_bytes(to_email: str, subject: str, body: str) -> bytes:
    lines = [
        f"To: {to_email}",
        f"Subject: {subject}",
        "Content-Type: text/plain; charset=utf-8",
    ]
    lines.append("")
    lines.append(body)
    return "\r\n".join(lines).encode("utf-8")


def command_draft_followup(args: argparse.Namespace) -> None:
    service = _gmail_service(args.account)
    subject = (
        args.subject or f"Follow-up - {datetime.now().astimezone().date().isoformat()}"
    )
    body = args.body or "Following up on this."
    raw = base64.urlsafe_b64encode(_draft_message_bytes(args.to, subject, body)).decode(
        "ascii"
    )
    payload = {"message": {"raw": raw}}
    result = _safe_execute(service.users().drafts().create(userId="me", body=payload))
    print(f"Draft created: {result.get('id')} to {args.to}")


def command_draft_reply(args: argparse.Namespace) -> None:
    service = _gmail_service(args.account)
    messages = _get_thread_messages(service, args.thread_id)
    if not messages:
        raise RuntimeError(f"Thread not found or empty: {args.thread_id}")
    latest = messages[-1]
    recipient = latest.from_email
    if not recipient:
        raise RuntimeError("Latest message has no sender email; cannot draft reply")
    subject = (
        latest.subject
        if latest.subject.lower().startswith("re:")
        else f"Re: {latest.subject}"
    )
    body = args.body or "Thanks, I will get back to you shortly."
    raw = base64.urlsafe_b64encode(
        _draft_message_bytes(recipient, subject, body)
    ).decode("ascii")
    payload = {"message": {"threadId": args.thread_id, "raw": raw}}
    result = _safe_execute(service.users().drafts().create(userId="me", body=payload))
    print(f"Draft reply created: {result.get('id')} in thread {args.thread_id}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read Gmail threads, create drafts only, and optionally sync email signals into the vault."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser(
        "auth", help="Authenticate and store a token for an account"
    )
    p_auth.add_argument("--account", choices=["private", "personal"], required=True)
    p_auth.set_defaults(func=lambda args: auth_account(args.account))

    p_search = sub.add_parser("search", help="Search Gmail threads")
    p_search.add_argument("--account", choices=["private", "personal"], required=True)
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--max-results", type=int, default=20)
    p_search.set_defaults(func=command_search)

    p_sum = sub.add_parser("summarize-thread", help="Summarize a Gmail thread")
    p_sum.add_argument("--account", choices=["private", "personal"], required=True)
    p_sum.add_argument("--thread-id", required=True)
    p_sum.add_argument("--to-inbox", action="store_true")
    p_sum.add_argument("--to-daily-brief", action="store_true")
    p_sum.add_argument("--dry-run", action="store_true")
    p_sum.set_defaults(func=command_summarize_thread)

    p_attachments = sub.add_parser(
        "download-attachments",
        help="Download attachments from a Gmail thread into the vault",
    )
    p_attachments.add_argument(
        "--account", choices=["private", "personal"], required=True
    )
    p_attachments.add_argument("--thread-id", required=True)
    p_attachments.add_argument("--output-dir", default="")
    p_attachments.add_argument("--dry-run", action="store_true")
    p_attachments.set_defaults(func=command_download_attachments)

    p_unanswered = sub.add_parser(
        "list-unanswered", help="List Inbox threads waiting on your reply"
    )
    p_unanswered.add_argument(
        "--account", choices=["private", "personal"], required=True
    )
    p_unanswered.add_argument("--max-results", type=int, default=20)
    p_unanswered.add_argument("--to-inbox", action="store_true")
    p_unanswered.add_argument("--to-daily-brief", action="store_true")
    p_unanswered.set_defaults(func=command_list_unanswered)

    p_today = sub.add_parser("list-today", help="List messages received today")
    p_today.add_argument("--account", choices=["private", "personal"], required=True)
    p_today.add_argument("--max-results", type=int, default=20)
    p_today.set_defaults(func=command_list_today)

    p_person = sub.add_parser(
        "list-by-person", help="List threads related to a person or email"
    )
    p_person.add_argument("--account", choices=["private", "personal"], required=True)
    p_person.add_argument("--person", required=True)
    p_person.add_argument("--max-results", type=int, default=20)
    p_person.set_defaults(func=command_list_by_person)

    p_reply = sub.add_parser(
        "draft-reply", help="Create a Gmail draft reply in an existing thread"
    )
    p_reply.add_argument("--account", choices=["private", "personal"], required=True)
    p_reply.add_argument("--thread-id", required=True)
    p_reply.add_argument("--body", default="")
    p_reply.set_defaults(func=command_draft_reply)

    p_followup = sub.add_parser("draft-followup", help="Create a Gmail follow-up draft")
    p_followup.add_argument("--account", choices=["private", "personal"], required=True)
    p_followup.add_argument("--to", required=True)
    p_followup.add_argument("--subject", default="")
    p_followup.add_argument("--body", default="")
    p_followup.set_defaults(func=command_draft_followup)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
