from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
INTEGRATION_DIR = REPO_ROOT / "90_System" / "Integrations" / "slack"
RUNTIME_DIR = INTEGRATION_DIR / "runtime"
CONFIG_PATH = INTEGRATION_DIR / "workspaces.json"
CONFIG_EXAMPLE_PATH = INTEGRATION_DIR / "workspaces.example.json"
INBOX_PATH = REPO_ROOT / "00_Mailbox" / "_Mailbox.md"
DAILY_BRIEFS_ROOT = REPO_ROOT / "10_DailyBriefs"
PEOPLE_DIR = REPO_ROOT / "40_People"
PEOPLE_INDEX_PATH = PEOPLE_DIR / "_PeopleIndex.md"

SLACK_DAILY_BRIEF_HEADING = "# Slack"
PRAGUE_TZ = ZoneInfo("Europe/Prague")
DEFAULT_ALLOWED_EXTENSIONS = [
    ".csv",
    ".doc",
    ".docx",
    ".jpeg",
    ".jpg",
    ".md",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".txt",
    ".xls",
    ".xlsx",
]
DEFAULT_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024
IGNORED_MESSAGE_SUBTYPES = {
    "bot_add",
    "channel_archive",
    "channel_join",
    "channel_leave",
    "channel_name",
    "channel_purpose",
    "channel_topic",
    "group_archive",
    "group_join",
    "group_leave",
    "group_name",
    "group_purpose",
    "group_topic",
    "me_message",
    "message_changed",
    "message_deleted",
    "pinned_item",
    "reply_broadcast",
    "slackbot_response",
    "thread_broadcast",
    "tombstone",
}


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
class WorkspaceDownloadPolicy:
    enabled: bool
    max_bytes: int
    allowed_extensions: tuple[str, ...]


@dataclass(frozen=True)
class ConversationConfig:
    id: str
    name: str
    kind: str
    retention_class: str
    allow_file_download: bool


@dataclass(frozen=True)
class WorkspaceConfig:
    alias: str
    team_id: str
    token_path: Path
    jan_user_ids: tuple[str, ...]
    allow_conversations: tuple[ConversationConfig, ...]
    download_policy: WorkspaceDownloadPolicy


@dataclass(frozen=True)
class SlackConversation:
    id: str
    name: str
    kind: str
    is_private: bool


@dataclass(frozen=True)
class SlackFile:
    id: str
    name: str
    mimetype: str
    size: int
    url_private_download: str


@dataclass(frozen=True)
class SlackMessage:
    ts: str
    thread_ts: str
    user_id: str
    username: str
    text: str
    subtype: str
    bot_id: str
    reply_count: int
    latest_reply: str
    files: tuple[SlackFile, ...]
    reactions: tuple[str, ...]
    edited: bool
    deleted: bool
    raw: dict[str, Any]


@dataclass(frozen=True)
class ConversationThread:
    workspace: str
    team_id: str
    conversation: ConversationConfig
    root_ts: str
    permalink: str
    messages: tuple[SlackMessage, ...]


def _yaml_quote(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _yaml_unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        inner = value[1:-1]
        if value[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


def _sanitize_filename(text: str) -> str:
    text = re.sub(r'[<>:"/\\\\|?*]+', "-", text.strip())
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return text[:120] if text else "Untitled"


def _safe_slug(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", text.strip())
    cleaned = re.sub(r"-{2,}", "-", cleaned).strip("-._")
    return cleaned or "item"


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
        data[key] = _yaml_unquote(raw_value) if raw_value else []
    return data


def _ensure_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


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
    return [line.rstrip() for line in match.group(1).strip().splitlines() if line.strip()]


def _merge_bullets(existing_lines: list[str], new_lines: list[str]) -> list[str]:
    return _dedupe_preserve_order([*existing_lines, *new_lines])


def _ensure_daily_brief_path(for_day: date) -> Path:
    path = DAILY_BRIEFS_ROOT / for_day.strftime("%Y") / for_day.strftime("%m") / f"{for_day.isoformat()}_Daily_Brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_to_daily_brief(lines: list[str]) -> None:
    if not lines:
        return
    path = _ensure_daily_brief_path(datetime.now(PRAGUE_TZ).date())
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    merged = _merge_bullets(_extract_section(existing, SLACK_DAILY_BRIEF_HEADING), lines)
    path.write_text(_replace_or_append_section(existing, SLACK_DAILY_BRIEF_HEADING, merged), encoding="utf-8")
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
    updated = text[:start] + "\n".join(lines) + "\n" + text[start:]
    INBOX_PATH.write_text(updated, encoding="utf-8")
    print(f"Updated Inbox: {INBOX_PATH}")


def _message_dt(ts: str) -> datetime:
    return datetime.fromtimestamp(float(ts), tz=PRAGUE_TZ)


def _days_back_to_oldest(days_back: int | None, *, default_days: int) -> str:
    days = default_days if days_back is None else max(1, days_back)
    return f"{(datetime.now(PRAGUE_TZ) - timedelta(days=days)).timestamp():.6f}"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        example = CONFIG_EXAMPLE_PATH if path == CONFIG_PATH else path
        raise RuntimeError(f"Missing Slack config: {path} (see {example})") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in {path}: {exc}") from exc


def load_workspace_configs() -> dict[str, WorkspaceConfig]:
    raw = _load_json(CONFIG_PATH)
    result: dict[str, WorkspaceConfig] = {}
    for item in raw.get("workspaces", []):
        alias = str(item.get("alias") or "").strip()
        if not alias:
            continue
        token_file = str(item.get("token_file") or "").strip()
        if not token_file:
            raise RuntimeError(f"Workspace '{alias}' is missing token_file")
        allow_conversations: list[ConversationConfig] = []
        for conv in item.get("allow_conversations", []) or []:
            conv_id = str(conv.get("id") or "").strip()
            if not conv_id:
                continue
            allow_conversations.append(
                ConversationConfig(
                    id=conv_id,
                    name=str(conv.get("name") or conv_id).strip(),
                    kind=str(conv.get("type") or "channel").strip(),
                    retention_class=str(conv.get("retention_class") or "standard").strip(),
                    allow_file_download=bool(conv.get("allow_file_download", False)),
                )
            )
        download = item.get("download", {}) or {}
        result[alias] = WorkspaceConfig(
            alias=alias,
            team_id=str(item.get("team_id") or "").strip(),
            token_path=(REPO_ROOT / token_file) if not Path(token_file).is_absolute() else Path(token_file),
            jan_user_ids=tuple(str(v).strip() for v in (item.get("jan_user_ids") or []) if str(v).strip()),
            allow_conversations=tuple(allow_conversations),
            download_policy=WorkspaceDownloadPolicy(
                enabled=bool(download.get("enabled", False)),
                max_bytes=int(download.get("max_bytes", DEFAULT_MAX_DOWNLOAD_BYTES) or DEFAULT_MAX_DOWNLOAD_BYTES),
                allowed_extensions=tuple(
                    str(v).strip().lower()
                    for v in (download.get("allowed_extensions") or DEFAULT_ALLOWED_EXTENSIONS)
                    if str(v).strip()
                ),
            ),
        )
    if not result:
        raise RuntimeError(f"No Slack workspaces configured in {CONFIG_PATH}")
    return result


def get_workspace_config(alias: str) -> WorkspaceConfig:
    configs = load_workspace_configs()
    if alias not in configs:
        raise RuntimeError(f"Unknown workspace alias '{alias}'. Configured: {', '.join(sorted(configs))}")
    return configs[alias]


class SlackClient:
    def __init__(self, workspace: WorkspaceConfig) -> None:
        self.workspace = workspace
        try:
            self._token = self.workspace.token_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError as exc:
            raise RuntimeError(f"Missing Slack token file: {self.workspace.token_path}") from exc
        if not self._token:
            raise RuntimeError(f"Slack token file is empty: {self.workspace.token_path}")
        self._user_cache: dict[str, dict[str, Any]] = {}

    def api_call(
        self,
        method: str,
        *,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        raw_url: str | None = None,
        binary: bool = False,
    ) -> tuple[Any, dict[str, str]]:
        query = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v not in {"", None}}, doseq=True)
        url = raw_url or f"https://slack.com/api/{method}"
        if query and raw_url is None:
            url += f"?{query}"
        body = None
        headers = {"Authorization": f"Bearer {self._token}"}
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(url, data=body, headers=headers)
        while True:
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}
                    raw = response.read()
                    if binary:
                        return raw, payload_headers
                    payload = json.loads(raw.decode("utf-8"))
                    if not payload.get("ok", False):
                        raise RuntimeError(f"Slack API error for {method}: {payload.get('error', 'unknown_error')}")
                    return payload, payload_headers
            except urllib.error.HTTPError as exc:
                if exc.code == 429:
                    retry_after = int(exc.headers.get("Retry-After", "1"))
                    time.sleep(max(1, retry_after))
                    continue
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"Slack API HTTP error for {method}: {exc.code} {detail}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"Slack API request failed for {method}: {exc}") from exc

    def auth_check(self) -> tuple[dict[str, Any], list[str]]:
        payload, headers = self.api_call("auth.test")
        scopes = [item.strip() for item in headers.get("x-oauth-scopes", "").split(",") if item.strip()]
        return payload, scopes

    def users(self) -> dict[str, dict[str, Any]]:
        if self._user_cache:
            return self._user_cache
        cursor = ""
        out: dict[str, dict[str, Any]] = {}
        while True:
            payload, _ = self.api_call("users.list", params={"cursor": cursor, "limit": 200})
            for member in payload.get("members", []) or []:
                user_id = str(member.get("id") or "").strip()
                if user_id:
                    out[user_id] = member
            cursor = str((payload.get("response_metadata") or {}).get("next_cursor") or "").strip()
            if not cursor:
                break
        self._user_cache = out
        return out

    def conversations(self, types: list[str] | None = None) -> list[SlackConversation]:
        cursor = ""
        out: list[SlackConversation] = []
        conv_types = ",".join(types or ["public_channel", "private_channel", "im", "mpim"])
        while True:
            payload, _ = self.api_call(
                "conversations.list",
                params={"cursor": cursor, "limit": 200, "types": conv_types, "exclude_archived": "true"},
            )
            for item in payload.get("channels", []) or []:
                out.append(
                    SlackConversation(
                        id=str(item.get("id") or ""),
                        name=_conversation_name(item),
                        kind=_conversation_kind(item),
                        is_private=bool(item.get("is_private", False)),
                    )
                )
            cursor = str((payload.get("response_metadata") or {}).get("next_cursor") or "").strip()
            if not cursor:
                break
        return out

    def conversation_history(self, conversation_id: str, *, oldest: str, latest: str | None = None) -> list[SlackMessage]:
        cursor = ""
        out: list[SlackMessage] = []
        while True:
            params = {"channel": conversation_id, "cursor": cursor, "limit": 200, "oldest": oldest}
            if latest:
                params["latest"] = latest
            payload, _ = self.api_call("conversations.history", params=params)
            out.extend(_normalize_message(item) for item in payload.get("messages", []) or [] if isinstance(item, dict))
            cursor = str((payload.get("response_metadata") or {}).get("next_cursor") or "").strip()
            if not cursor:
                break
        return sorted(out, key=lambda item: float(item.ts))

    def conversation_replies(self, conversation_id: str, *, thread_ts: str) -> list[SlackMessage]:
        cursor = ""
        out: list[SlackMessage] = []
        while True:
            payload, _ = self.api_call(
                "conversations.replies",
                params={"channel": conversation_id, "ts": thread_ts, "cursor": cursor, "limit": 200},
            )
            out.extend(_normalize_message(item) for item in payload.get("messages", []) or [] if isinstance(item, dict))
            cursor = str((payload.get("response_metadata") or {}).get("next_cursor") or "").strip()
            if not cursor:
                break
        return sorted(out, key=lambda item: float(item.ts))

    def permalink(self, conversation_id: str, message_ts: str) -> str:
        payload, _ = self.api_call("chat.getPermalink", params={"channel": conversation_id, "message_ts": message_ts})
        return str(payload.get("permalink") or "")

    def download_file(self, file: SlackFile) -> bytes:
        raw, _ = self.api_call("files.download", raw_url=file.url_private_download, binary=True)
        return raw


def _conversation_kind(payload: dict[str, Any]) -> str:
    if payload.get("is_im"):
        return "im"
    if payload.get("is_mpim"):
        return "mpim"
    if payload.get("is_private"):
        return "private_channel"
    return "public_channel"


def _conversation_name(payload: dict[str, Any]) -> str:
    if payload.get("is_im"):
        return str(payload.get("user") or payload.get("id") or "dm")
    return str(payload.get("name") or payload.get("id") or "conversation")


def _normalize_message(raw: dict[str, Any]) -> SlackMessage:
    files = tuple(
        SlackFile(
            id=str(item.get("id") or ""),
            name=str(item.get("name") or item.get("title") or "file"),
            mimetype=str(item.get("mimetype") or item.get("filetype") or ""),
            size=int(item.get("size") or 0),
            url_private_download=str(item.get("url_private_download") or item.get("url_private") or ""),
        )
        for item in (raw.get("files") or [])
        if isinstance(item, dict)
    )
    reactions = tuple(
        f":{str(item.get('name') or '').strip()}: x{int(item.get('count') or 0)}"
        for item in (raw.get("reactions") or [])
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    )
    subtype = str(raw.get("subtype") or "").strip()
    previous = raw.get("previous_message")
    deleted = subtype == "message_deleted" or bool(previous and str(previous.get("text") or "").strip() == "")
    edited = bool(raw.get("edited"))
    return SlackMessage(
        ts=str(raw.get("ts") or ""),
        thread_ts=str(raw.get("thread_ts") or raw.get("ts") or ""),
        user_id=str(raw.get("user") or ""),
        username=str(raw.get("username") or ""),
        text=_message_text(raw),
        subtype=subtype,
        bot_id=str(raw.get("bot_id") or ""),
        reply_count=int(raw.get("reply_count") or 0),
        latest_reply=str(raw.get("latest_reply") or ""),
        files=files,
        reactions=reactions,
        edited=edited,
        deleted=deleted,
        raw=raw,
    )


def _message_text(raw: dict[str, Any]) -> str:
    text = str(raw.get("text") or "").replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
    text = re.sub(r"<@([A-Z0-9]+)>", r"@\1", text)
    text = re.sub(r"<#([A-Z0-9]+)\|([^>]+)>", r"#\2", text)
    text = re.sub(r"<([^>|]+)\|([^>]+)>", r"\2 (\1)", text)
    text = re.sub(r"<([^>]+)>", r"\1", text)
    return text.strip()


def _user_label(user_map: dict[str, dict[str, Any]], message: SlackMessage) -> str:
    if message.user_id and message.user_id in user_map:
        user = user_map[message.user_id]
        profile = user.get("profile") or {}
        return (
            str(profile.get("real_name") or "").strip()
            or str(profile.get("display_name") or "").strip()
            or str(user.get("name") or "").strip()
            or message.user_id
        )
    if message.username:
        return message.username
    if message.bot_id:
        return f"bot:{message.bot_id}"
    return "unknown"


def _is_human_message(message: SlackMessage) -> bool:
    if not message.ts:
        return False
    if message.bot_id:
        return False
    if message.subtype in IGNORED_MESSAGE_SUBTYPES:
        return False
    return True


def _root_candidates(messages: list[SlackMessage], conversation: ConversationConfig) -> list[SlackMessage]:
    if conversation.kind in {"im", "mpim"}:
        return [message for message in messages if _is_human_message(message)]
    out: list[SlackMessage] = []
    for message in messages:
        if not _is_human_message(message):
            continue
        if message.ts == message.thread_ts or message.reply_count > 0:
            out.append(message)
    return out


def _thread_messages(client: SlackClient, conversation: ConversationConfig, root: SlackMessage) -> list[SlackMessage]:
    if conversation.kind in {"im", "mpim"} and root.reply_count == 0 and root.thread_ts == root.ts:
        return [root]
    if root.reply_count > 0 or root.thread_ts != root.ts:
        replies = client.conversation_replies(conversation.id, thread_ts=root.thread_ts)
        if replies:
            return replies
    return [root]


def collect_threads(
    workspace: WorkspaceConfig,
    *,
    oldest: str,
    latest: str | None = None,
    conversation_ids: set[str] | None = None,
) -> list[ConversationThread]:
    client = SlackClient(workspace)
    items: list[ConversationThread] = []
    for conversation in workspace.allow_conversations:
        if conversation_ids and conversation.id not in conversation_ids:
            continue
        history = client.conversation_history(conversation.id, oldest=oldest, latest=latest)
        for root in _root_candidates(history, conversation):
            messages = _thread_messages(client, conversation, root)
            if not messages:
                continue
            items.append(
                ConversationThread(
                    workspace=workspace.alias,
                    team_id=workspace.team_id,
                    conversation=conversation,
                    root_ts=messages[0].thread_ts or messages[0].ts,
                    permalink=client.permalink(conversation.id, messages[0].thread_ts or messages[0].ts),
                    messages=tuple(messages),
                )
            )
    deduped: dict[tuple[str, str], ConversationThread] = {}
    for item in items:
        key = (item.conversation.id, item.root_ts)
        existing = deduped.get(key)
        if existing is None or float(item.messages[-1].ts) > float(existing.messages[-1].ts):
            deduped[key] = item
    return sorted(deduped.values(), key=lambda item: float(item.messages[-1].ts), reverse=True)


def runtime_state_path(alias: str) -> Path:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    return RUNTIME_DIR / f"{alias}_state.json"


def load_runtime_state(alias: str) -> dict[str, Any]:
    path = runtime_state_path(alias)
    if not path.exists():
        return {"conversations": {}}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"conversations": {}}


def save_runtime_state(alias: str, state: dict[str, Any]) -> None:
    path = runtime_state_path(alias)
    path.write_text(json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")


def people_lookup() -> tuple[dict[str, Path], dict[str, Path]]:
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


def find_matching_person(
    user_map: dict[str, dict[str, Any]],
    message: SlackMessage,
    by_email: dict[str, Path],
    by_alias: dict[str, Path],
) -> str:
    user = user_map.get(message.user_id, {})
    profile = user.get("profile") or {}
    email_addr = str(profile.get("email") or "").strip().casefold()
    if email_addr and email_addr in by_email:
        return by_email[email_addr].stem
    for candidate in [
        str(profile.get("real_name") or "").strip(),
        str(profile.get("display_name") or "").strip(),
        str(user.get("name") or "").strip(),
    ]:
        if candidate and candidate.casefold() in by_alias:
            return by_alias[candidate.casefold()].stem
    return ""


def summarize_thread_text(workspace: WorkspaceConfig, thread: ConversationThread) -> str:
    client = SlackClient(workspace)
    user_map = client.users()
    lines = [
        f"Workspace: {workspace.alias}",
        f"Conversation: {thread.conversation.name} ({thread.conversation.kind})",
        f"Thread root: {thread.root_ts}",
        f"Messages: {len(thread.messages)}",
        f"Last message: {_message_dt(thread.messages[-1].ts).isoformat(timespec='minutes')}",
        f"Permalink: {thread.permalink or '(unavailable)'}",
        "",
    ]
    for message in thread.messages:
        label = _user_label(user_map, message)
        stamp = _message_dt(message.ts).isoformat(timespec="minutes")
        text = re.sub(r"\s+", " ", message.text).strip() or "(No text)"
        lines.append(f"- {stamp} | {label}: {text}")
    return "\n".join(lines)


def list_unanswered_threads(
    workspace: WorkspaceConfig,
    *,
    days_back: int | None,
    max_results: int,
    include_dm: bool,
    include_mpim: bool,
) -> list[ConversationThread]:
    oldest = _days_back_to_oldest(days_back, default_days=7)
    threads = collect_threads(workspace, oldest=oldest)
    jan_ids = set(workspace.jan_user_ids)
    result: list[ConversationThread] = []
    for thread in threads:
        if thread.conversation.kind == "im" and not include_dm:
            continue
        if thread.conversation.kind == "mpim" and not include_mpim:
            continue
        human_messages = [msg for msg in thread.messages if _is_human_message(msg)]
        if not human_messages:
            continue
        latest = human_messages[-1]
        if latest.user_id and latest.user_id in jan_ids:
            continue
        result.append(thread)
        if len(result) >= max_results:
            break
    return result


def _render_slack_lines_for_inbox(prefix: str, threads: list[ConversationThread]) -> list[str]:
    now = datetime.now(PRAGUE_TZ).strftime("%Y-%m-%d %H:%M")
    lines: list[str] = []
    for thread in threads:
        latest = thread.messages[-1]
        preview = re.sub(r"\s+", " ", latest.text).strip()[:120] or "(No text)"
        lines.append(f"`{now}` - {prefix}: {thread.conversation.name} - {preview}")
    return lines


def command_auth_check(args: argparse.Namespace) -> None:
    workspace = get_workspace_config(args.workspace)
    payload, scopes = SlackClient(workspace).auth_check()
    print(f"Workspace: {workspace.alias}")
    print(f"Team: {payload.get('team')} ({payload.get('team_id')})")
    print(f"User: {payload.get('user')} ({payload.get('user_id')})")
    print(f"Configured team_id: {workspace.team_id or '(not set)'}")
    print(f"Scopes: {', '.join(scopes) if scopes else '(header unavailable)'}")


def command_list_conversations(args: argparse.Namespace) -> None:
    workspace = get_workspace_config(args.workspace)
    types = [item.strip() for item in args.types.split(",") if item.strip()]
    conversations = SlackClient(workspace).conversations(types or None)
    for item in conversations:
        print(f"{item.id} | {item.kind} | {item.name}")
    print(f"Conversations found: {len(conversations)}")


def command_search(args: argparse.Namespace) -> None:
    workspace = get_workspace_config(args.workspace)
    oldest = _days_back_to_oldest(args.days_back, default_days=14)
    conversation_ids = {args.conversation} if args.conversation else None
    query = args.query.casefold()
    client = SlackClient(workspace)
    user_map = client.users()
    by_email, by_alias = people_lookup()
    matched = 0
    for thread in collect_threads(workspace, oldest=oldest, conversation_ids=conversation_ids):
        if matched >= args.max_results:
            break
        haystack = " ".join(
            [
                thread.conversation.name,
                thread.permalink,
                " ".join(message.text for message in thread.messages),
                " ".join(find_matching_person(user_map, message, by_email, by_alias) for message in thread.messages),
            ]
        ).casefold()
        if query not in haystack:
            continue
        latest = thread.messages[-1]
        preview = re.sub(r"\s+", " ", latest.text).strip()[:180] or "(No text)"
        print(f"{_message_dt(latest.ts).isoformat(timespec='minutes')} | {thread.conversation.name} | {thread.root_ts} | {preview}")
        matched += 1
    print(f"Threads matched: {matched}")


def _find_thread(workspace: WorkspaceConfig, conversation_id: str, thread_ts: str) -> ConversationThread:
    conversation = next((item for item in workspace.allow_conversations if item.id == conversation_id), None)
    if conversation is None:
        raise RuntimeError(f"Conversation '{conversation_id}' is not allowlisted for workspace '{workspace.alias}'")
    client = SlackClient(workspace)
    messages = client.conversation_replies(conversation_id, thread_ts=thread_ts)
    if not messages:
        messages = client.conversation_history(conversation_id, oldest=thread_ts, latest=thread_ts)
    if not messages:
        raise RuntimeError(f"Thread not found: {conversation_id} {thread_ts}")
    return ConversationThread(
        workspace=workspace.alias,
        team_id=workspace.team_id,
        conversation=conversation,
        root_ts=thread_ts,
        permalink=client.permalink(conversation_id, thread_ts),
        messages=tuple(messages),
    )


def _eligible_file(workspace: WorkspaceConfig, conversation: ConversationConfig, file: SlackFile) -> tuple[bool, str]:
    if not workspace.download_policy.enabled:
        return False, "workspace download disabled"
    if not conversation.allow_file_download:
        return False, "conversation download disabled"
    ext = Path(file.name).suffix.lower()
    if ext and ext not in workspace.download_policy.allowed_extensions:
        return False, f"blocked extension {ext}"
    if file.size > workspace.download_policy.max_bytes:
        return False, f"file too large ({file.size} bytes)"
    if not file.url_private_download:
        return False, "missing download URL"
    return True, ""


def _attachment_output_dir(workspace: WorkspaceConfig, thread: ConversationThread, explicit_dir: str | None) -> Path:
    if explicit_dir:
        path = Path(explicit_dir)
        return path if path.is_absolute() else REPO_ROOT / path
    thread_day = _message_dt(thread.messages[-1].ts)
    return (
        REPO_ROOT
        / "00_Mailbox"
        / thread_day.strftime("%Y")
        / thread_day.strftime("%m")
        / thread_day.strftime("%d")
        / "attachments"
        / "slack"
        / _safe_slug(workspace.alias)
        / _safe_slug(thread.conversation.name)
        / _safe_slug(thread.root_ts.replace(".", "_"))
    )


def command_summarize_thread(args: argparse.Namespace) -> None:
    workspace = get_workspace_config(args.workspace)
    thread = _find_thread(workspace, args.conversation, args.thread_ts)
    print(summarize_thread_text(workspace, thread))
    if args.dry_run:
        if args.to_inbox:
            print(f"Would append Slack thread summary to Inbox: {thread.root_ts}")
        if args.to_daily_brief:
            print(f"Would append Slack thread summary to Daily Brief: {thread.root_ts}")
        return
    if args.to_inbox:
        _append_to_inbox(_render_slack_lines_for_inbox("Slack thread", [thread]))
    if args.to_daily_brief:
        _append_to_daily_brief([f"- Slack thread: {thread.conversation.name} ({thread.root_ts})"])


def command_download_files(args: argparse.Namespace) -> None:
    workspace = get_workspace_config(args.workspace)
    thread = _find_thread(workspace, args.conversation, args.thread_ts)
    client = SlackClient(workspace)
    target_dir = _attachment_output_dir(workspace, thread, args.output_dir or None)
    seen_names: dict[str, int] = {}
    processed = 0
    for message in thread.messages:
        for file in message.files:
            allowed, reason = _eligible_file(workspace, thread.conversation, file)
            if not allowed:
                print(f"Skipped: {file.name} ({reason})")
                continue
            base_name = _sanitize_filename(file.name)
            seen_count = seen_names.get(base_name.casefold(), 0)
            seen_names[base_name.casefold()] = seen_count + 1
            stem = Path(base_name).stem
            ext = Path(base_name).suffix
            output_name = base_name if seen_count == 0 else f"{stem}_{seen_count + 1}{ext}"
            destination = target_dir / output_name
            if args.dry_run:
                print(f"Would save: {destination} ({file.mimetype}, {file.size} bytes)")
            else:
                target_dir.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(client.download_file(file))
                print(f"Saved: {destination} ({file.mimetype}, {file.size} bytes)")
            processed += 1
    if processed == 0:
        print("No eligible files found in thread.")
        return
    print(f"Files processed: {processed}")


def command_list_unanswered(args: argparse.Namespace) -> None:
    workspace = get_workspace_config(args.workspace)
    threads = list_unanswered_threads(
        workspace,
        days_back=args.days_back,
        max_results=args.max_results,
        include_dm=args.include_dm,
        include_mpim=args.include_mpim,
    )
    for thread in threads:
        latest = thread.messages[-1]
        preview = re.sub(r"\s+", " ", latest.text).strip()[:180] or "(No text)"
        print(f"{_message_dt(latest.ts).isoformat(timespec='minutes')} | {thread.conversation.name} | {thread.root_ts} | waiting on reply | {preview}")
    print(f"Unanswered Slack threads: {len(threads)}")
    if args.to_inbox:
        _append_to_inbox(_render_slack_lines_for_inbox("Slack follow-up", threads))
    if args.to_daily_brief:
        _append_to_daily_brief([f"- Slack follow-up: {thread.conversation.name} ({thread.root_ts})" for thread in threads])


def command_list_by_person(args: argparse.Namespace) -> None:
    workspace = get_workspace_config(args.workspace)
    oldest = _days_back_to_oldest(args.days_back, default_days=30)
    client = SlackClient(workspace)
    user_map = client.users()
    query = args.person.casefold()
    matched_ids = {
        user_id
        for user_id, payload in user_map.items()
        if query
        in " ".join(
            [
                str(payload.get("name") or ""),
                str((payload.get("profile") or {}).get("real_name") or ""),
                str((payload.get("profile") or {}).get("display_name") or ""),
                str((payload.get("profile") or {}).get("email") or ""),
            ]
        ).casefold()
    }
    matched = 0
    for thread in collect_threads(workspace, oldest=oldest):
        if matched >= args.max_results:
            break
        if not any(message.user_id in matched_ids for message in thread.messages):
            continue
        latest = thread.messages[-1]
        print(f"{_message_dt(latest.ts).isoformat(timespec='minutes')} | {thread.conversation.name} | {thread.root_ts}")
        matched += 1
    print(f"Threads matched: {matched}")


def command_draft_not_enabled(args: argparse.Namespace) -> None:
    raise RuntimeError("Slack write support is not enabled. Configure a separate write-capable app before using draft/post commands.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read Slack data safely and optionally export signals into the vault.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_auth = sub.add_parser("auth-check", help="Validate Slack token and report scopes")
    p_auth.add_argument("--workspace", required=True)
    p_auth.set_defaults(func=command_auth_check)

    p_conversations = sub.add_parser("list-conversations", help="List accessible Slack conversations")
    p_conversations.add_argument("--workspace", required=True)
    p_conversations.add_argument("--types", default="public_channel,private_channel,im,mpim")
    p_conversations.set_defaults(func=command_list_conversations)

    p_search = sub.add_parser("search", help="Search allowlisted Slack threads by text")
    p_search.add_argument("--workspace", required=True)
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--conversation", default="")
    p_search.add_argument("--days-back", type=int, default=None)
    p_search.add_argument("--max-results", type=int, default=20)
    p_search.set_defaults(func=command_search)

    p_summary = sub.add_parser("summarize-thread", help="Summarize one Slack thread")
    p_summary.add_argument("--workspace", required=True)
    p_summary.add_argument("--conversation", required=True)
    p_summary.add_argument("--thread-ts", required=True)
    p_summary.add_argument("--to-inbox", action="store_true")
    p_summary.add_argument("--to-daily-brief", action="store_true")
    p_summary.add_argument("--dry-run", action="store_true")
    p_summary.set_defaults(func=command_summarize_thread)

    p_download = sub.add_parser("download-files", help="Download eligible files from a Slack thread into the vault")
    p_download.add_argument("--workspace", required=True)
    p_download.add_argument("--conversation", required=True)
    p_download.add_argument("--thread-ts", required=True)
    p_download.add_argument("--output-dir", default="")
    p_download.add_argument("--dry-run", action="store_true")
    p_download.set_defaults(func=command_download_files)

    p_unanswered = sub.add_parser("list-unanswered", help="List Slack threads waiting on your reply")
    p_unanswered.add_argument("--workspace", required=True)
    p_unanswered.add_argument("--days-back", type=int, default=None)
    p_unanswered.add_argument("--max-results", type=int, default=20)
    p_unanswered.add_argument("--include-dm", action="store_true")
    p_unanswered.add_argument("--include-mpim", action="store_true")
    p_unanswered.add_argument("--to-inbox", action="store_true")
    p_unanswered.add_argument("--to-daily-brief", action="store_true")
    p_unanswered.set_defaults(func=command_list_unanswered)

    p_person = sub.add_parser("list-by-person", help="List Slack threads by person/email")
    p_person.add_argument("--workspace", required=True)
    p_person.add_argument("--person", required=True)
    p_person.add_argument("--days-back", type=int, default=None)
    p_person.add_argument("--max-results", type=int, default=20)
    p_person.set_defaults(func=command_list_by_person)

    p_draft = sub.add_parser("draft-message", help="Reserved for future separate write-capable Slack app")
    p_draft.add_argument("--workspace", required=True)
    p_draft.set_defaults(func=command_draft_not_enabled)

    p_reply = sub.add_parser("draft-reply", help="Reserved for future separate write-capable Slack app")
    p_reply.add_argument("--workspace", required=True)
    p_reply.set_defaults(func=command_draft_not_enabled)

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
