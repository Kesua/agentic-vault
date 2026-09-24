#!/usr/bin/env python3
"""Workblock protocol helper using only the Python standard library."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any, Iterable


STATUSES = {"active", "blocked", "completed"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}
REQUIRED_FIELDS = {"type", "status", "scope", "created", "updated", "backfilled"}
REQUIRED_BODY_LABELS = (
    "Goal",
    "Current state",
    "Next action",
    "Blocker / decision",
    "Key files",
    "Source sessions",
)
IGNORED_WORKBLOCK_FILES = {"README.md", "_Template.md"}
INVALID_WINDOWS_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
WINDOWS_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{number}" for number in range(1, 10)),
    *(f"LPT{number}" for number in range(1, 10)),
}
TOKEN_RE = re.compile(r"[\w-]+", re.UNICODE)


def atomic_write_text(path: Path, content: str) -> None:
    """Replace a text file atomically using a temporary sibling."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(Path(path), json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    normalized = markdown.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return {}, normalized.strip()
    end = normalized.find("\n---\n", 4)
    if end < 0:
        return {}, normalized.strip()
    raw = normalized[4:end]
    parsed: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        scalar = value.strip()
        if len(scalar) >= 2 and scalar[0] == scalar[-1] and scalar[0] in {'"', "'"}:
            scalar = scalar[1:-1]
        parsed[key.strip()] = scalar
    return parsed, normalized[end + 5 :].strip()


def parse_workblock(path: Path) -> dict[str, Any]:
    metadata, body = parse_frontmatter(Path(path).read_text(encoding="utf-8-sig"))
    heading_match = re.search(r"^#\s+(.+?)\s*$", body, flags=re.MULTILINE)
    return {
        "path": Path(path),
        "metadata": metadata,
        "body": body,
        "heading": heading_match.group(1).strip() if heading_match else "",
    }


def _is_iso_date(value: str) -> bool:
    try:
        dt.date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


def _is_iso_datetime(value: str) -> bool:
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    return parsed.tzinfo is not None


def _as_bool(value: str) -> bool | None:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def _issue(path: Path, message: str) -> dict[str, str]:
    return {"path": str(path), "message": message}


def validate_workblocks(root: Path) -> dict[str, Any]:
    root = Path(root)
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    paths = [
        path
        for path in sorted(root.glob("*.md"), key=lambda item: item.name.casefold())
        if path.name not in IGNORED_WORKBLOCK_FILES
    ] if root.exists() else []

    seen_names: dict[str, Path] = {}
    for path in paths:
        name_key = unicodedata.normalize("NFKC", path.name).casefold()
        if name_key in seen_names:
            errors.append(_issue(path, f"duplicate filename (case-insensitive): {seen_names[name_key].name}"))
        else:
            seen_names[name_key] = path

        if len(path.name) > 120:
            warnings.append(_issue(path, "filename is longer than the 120-character convention"))

        try:
            block = parse_workblock(path)
        except (OSError, UnicodeError) as exc:
            errors.append(_issue(path, f"cannot read workblock: {exc}"))
            continue
        metadata = block["metadata"]
        body = block["body"]

        for field in sorted(REQUIRED_FIELDS - metadata.keys()):
            errors.append(_issue(path, f"missing required frontmatter field: {field}"))
        if metadata.get("type") != "workblock":
            errors.append(_issue(path, "type must be 'workblock'"))
        if metadata.get("status") not in STATUSES:
            errors.append(_issue(path, "status must be active, blocked, or completed"))
        if not metadata.get("scope"):
            errors.append(_issue(path, "scope must be a wikilink or 'general'"))
        elif metadata["scope"] != "general" and not re.fullmatch(r"\[\[[^\]]+\]\]", metadata["scope"]):
            errors.append(_issue(path, "scope must be a wikilink or 'general'"))
        if not _is_iso_date(metadata.get("created", "")):
            errors.append(_issue(path, "created must be an ISO date (YYYY-MM-DD)"))
        if not _is_iso_datetime(metadata.get("updated", "")):
            errors.append(_issue(path, "updated must be an ISO datetime with timezone"))
        backfilled = _as_bool(metadata.get("backfilled", ""))
        if backfilled is None:
            errors.append(_issue(path, "backfilled must be true or false"))
        confidence = metadata.get("confidence", "")
        if backfilled and confidence not in CONFIDENCE_LEVELS:
            errors.append(_issue(path, "confidence is required for backfilled workblocks and must be high, medium, or low"))
        elif confidence and confidence not in CONFIDENCE_LEVELS:
            errors.append(_issue(path, "confidence must be high, medium, or low"))

        first_content_line = next((line.strip() for line in body.splitlines() if line.strip()), "")
        if not first_content_line.startswith("# "):
            errors.append(_issue(path, "body must start with a level-1 heading"))
        for label in REQUIRED_BODY_LABELS:
            if not re.search(rf"^-\s+{re.escape(label)}:\s*", body, flags=re.MULTILINE):
                errors.append(_issue(path, f"missing body field: {label}"))

    return {"checked": len(paths), "errors": errors, "warnings": warnings}


def _tokens(value: str) -> set[str]:
    return {token.casefold() for token in TOKEN_RE.findall(value) if len(token) > 1}


def find_workblocks(root: Path, statuses: set[str], query: str = "") -> list[dict[str, Any]]:
    query_tokens = _tokens(query)
    results: list[dict[str, Any]] = []
    for path in sorted(Path(root).glob("*.md"), key=lambda item: item.name.casefold()):
        if path.name in IGNORED_WORKBLOCK_FILES:
            continue
        try:
            block = parse_workblock(path)
        except (OSError, UnicodeError):
            continue
        if block["metadata"].get("status") not in statuses:
            continue
        name_tokens = _tokens(path.stem)
        heading_tokens = _tokens(block["heading"])
        body_tokens = _tokens(block["body"])
        if query_tokens:
            matched = query_tokens & body_tokens
            if not matched:
                continue
            score = 6 * len(query_tokens & name_tokens) + 4 * len(query_tokens & heading_tokens) + len(matched)
        else:
            score = 0
        results.append(
            {
                "path": path,
                "status": block["metadata"].get("status"),
                "scope": block["metadata"].get("scope"),
                "updated": block["metadata"].get("updated"),
                "heading": block["heading"],
                "score": score,
            }
        )
    results.sort(key=lambda item: (-item["score"], str(item["path"]).casefold()))
    return results


def _safe_component(value: str) -> str:
    value = INVALID_WINDOWS_CHARS.sub("-", value)
    value = re.sub(r"\s+", " ", value).strip(" .-")
    if not value:
        value = "Untitled"
    if value.upper() in WINDOWS_RESERVED:
        value = f"_{value}"
    return value


def safe_filename(
    scope: str,
    intent: str,
    session_id: str,
    existing_names: Iterable[str],
    max_length: int = 120,
) -> str:
    scope_part = _safe_component(scope)
    intent_part = _safe_component(intent)
    suffix = ".md"
    base = f"{scope_part} - {intent_part}"
    available = max_length - len(suffix)
    if len(base) > available:
        base = base[:available].rstrip(" .-")
    existing = {name.casefold() for name in existing_names}
    candidate = f"{base}{suffix}"
    if candidate.casefold() not in existing:
        return candidate
    collision = _safe_component(session_id)[:8] or "session"
    collision_suffix = f" - {collision}"
    trimmed = base[: available - len(collision_suffix)].rstrip(" .-")
    return f"{trimmed}{collision_suffix}{suffix}"


SECRET_PATTERNS = (
    re.compile(r"(?im)^(\s*authorization\s*:\s*)(?:bearer|basic)\s+\S+"),
    re.compile(r"(?i)\b(?:sk|rk|pk)-(?:test_|live_)?[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"(?i)(\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret|password|passwd|pwd)\b\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b"),
)


def redact_secrets(text: str) -> str:
    redacted = text
    redacted = SECRET_PATTERNS[0].sub(r"\1[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[1].sub("[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[2].sub(r"\1[REDACTED]", redacted)
    redacted = SECRET_PATTERNS[3].sub("[REDACTED]", redacted)
    return redacted


def _normalized_path(path: str | Path) -> str:
    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError):
        resolved = Path(os.path.abspath(os.fspath(path)))
    return os.path.normcase(str(resolved)).rstrip("\\/")


def _read_json_lines(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def _load_codex_titles(path: Path | None) -> dict[str, str]:
    titles: dict[str, str] = {}
    if not path or not path.exists():
        return titles
    for row in _read_json_lines(path):
        session_id = str(row.get("id", ""))
        title = str(row.get("thread_name", "")).strip()
        if session_id and title:
            titles[session_id] = redact_secrets(title)
    return titles


def _contains_subagent(value: Any) -> bool:
    if isinstance(value, str):
        return "subagent" in value.casefold()
    if isinstance(value, dict):
        return any("subagent" in str(key).casefold() or _contains_subagent(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_subagent(item) for item in value)
    return False


def _classify_codex(path: Path, vault_root: Path, titles: dict[str, str]) -> tuple[dict[str, Any], str | None]:
    meta: dict[str, Any] | None = None
    first_timestamp = ""
    for row in _read_json_lines(path):
        if not first_timestamp:
            first_timestamp = str(row.get("timestamp", ""))
        if row.get("type") == "session_meta" and isinstance(row.get("payload"), dict):
            meta = row["payload"]
            break
    if not meta:
        return {"provider": "codex", "source_path": str(path)}, "missing_metadata"
    session_id = str(meta.get("session_id") or meta.get("id") or path.stem)
    item = {
        "key": f"codex:{session_id}",
        "provider": "codex",
        "session_id": session_id,
        "timestamp": str(meta.get("timestamp") or first_timestamp),
        "title": titles.get(session_id, ""),
        "source_path": str(path),
    }
    if _normalized_path(meta.get("cwd", "")) != _normalized_path(vault_root):
        return item, "cwd"
    thread_source = meta.get("thread_source")
    thread_text = str(thread_source).casefold()
    if "automation" in thread_text:
        return item, "automation"
    if "guardian_review" in thread_text or "guardian" == thread_text:
        return item, "guardian_review"
    if "subagent" in thread_text or _contains_subagent(meta.get("source")):
        return item, "subagent"
    source = str(meta.get("source", "")).casefold()
    originator = str(meta.get("originator", "")).casefold()
    if source == "exec" or "codex_exec" in originator:
        return item, "codex_exec"
    return item, None


def _claude_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    direct = list(root.glob("*.jsonl"))
    if direct:
        return sorted(direct)
    return sorted(path for project in root.iterdir() if project.is_dir() for path in project.glob("*.jsonl"))


def _classify_claude(path: Path, vault_root: Path) -> tuple[dict[str, Any], str | None]:
    session_id = path.stem
    cwd = ""
    timestamp = ""
    sidechain = False
    for row in _read_json_lines(path):
        session_id = str(row.get("sessionId") or session_id)
        cwd = str(row.get("cwd") or cwd)
        timestamp = str(row.get("timestamp") or timestamp)
        sidechain = sidechain or row.get("isSidechain") is True
        if cwd and timestamp and sidechain:
            break
    item = {
        "key": f"claude:{session_id}",
        "provider": "claude",
        "session_id": session_id,
        "timestamp": timestamp,
        "title": "",
        "source_path": str(path),
    }
    if sidechain:
        return item, "sidechain"
    return item, None


def _default_claude_root(vault_root: Path) -> Path:
    project_name = re.sub(r"[^A-Za-z0-9]", "-", str(Path(vault_root).resolve()))
    return Path.home() / ".claude" / "projects" / project_name


def _default_codex_root() -> Path:
    return Path.home() / ".codex" / "sessions"


def index_history(
    vault_root: Path,
    output: Path,
    *,
    claude_root: Path | None = None,
    codex_root: Path | None = None,
    codex_index: Path | None = None,
) -> dict[str, Any]:
    vault_root = Path(vault_root).resolve()
    output = Path(output)
    claude_root = Path(claude_root) if claude_root is not None else _default_claude_root(vault_root)
    codex_root = Path(codex_root) if codex_root is not None else _default_codex_root()
    if codex_index is None:
        codex_index = Path.home() / ".codex" / "session_index.jsonl"
    titles = _load_codex_titles(Path(codex_index))

    eligible_by_key: dict[str, dict[str, Any]] = {}
    excluded: list[dict[str, Any]] = []
    scanned = 0

    codex_paths = sorted(codex_root.rglob("*.jsonl")) if codex_root.exists() else []
    for path in codex_paths:
        scanned += 1
        item, reason = _classify_codex(path, vault_root, titles)
        key = item.get("key", f"codex-file:{path}")
        if reason:
            excluded.append({**item, "reason": reason})
        elif key in eligible_by_key:
            excluded.append({**item, "reason": "duplicate"})
        else:
            eligible_by_key[key] = item

    for path in _claude_files(claude_root):
        scanned += 1
        item, reason = _classify_claude(path, vault_root)
        key = item["key"]
        if reason:
            excluded.append({**item, "reason": reason})
        elif key in eligible_by_key:
            excluded.append({**item, "reason": "duplicate"})
        else:
            eligible_by_key[key] = item

    eligible = sorted(
        eligible_by_key.values(), key=lambda item: (item.get("timestamp", ""), item["key"])
    )
    excluded.sort(key=lambda item: (item.get("provider", ""), item.get("source_path", "")))
    manifest = {
        "version": 1,
        "vault_root": str(vault_root),
        "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "eligible": eligible,
        "excluded": excluded,
        "counts": {
            "scanned": scanned,
            "eligible": len(eligible),
            "excluded": len(excluded),
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output / "manifest.json", manifest)

    state_path = output / "state.json"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            state = {}
    else:
        state = {}
    sessions = state.get("sessions") if isinstance(state.get("sessions"), dict) else {}
    valid_keys = {item["key"] for item in eligible}
    sessions = {key: value for key, value in sessions.items() if key in valid_keys}
    state = {
        "version": 1,
        "manifest": "manifest.json",
        "batch_size": 20,
        "sessions": sessions,
    }
    atomic_write_json(state_path, state)
    return manifest


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if isinstance(text, str):
                    parts.append(text)
        return "\n".join(parts)
    return ""


def _extract_session(item: dict[str, Any], redact: bool) -> dict[str, Any]:
    messages: list[dict[str, str]] = []
    path = Path(item["source_path"])
    for row in _read_json_lines(path):
        role = ""
        content: Any = ""
        if item["provider"] == "codex" and row.get("type") == "response_item":
            payload = row.get("payload", {})
            if isinstance(payload, dict) and payload.get("type") == "message":
                role = str(payload.get("role", ""))
                content = payload.get("content", "")
        elif item["provider"] == "claude":
            if row.get("type") in {"user", "assistant"}:
                message = row.get("message", {})
                if isinstance(message, dict):
                    role = str(message.get("role") or row.get("type"))
                    content = message.get("content", "")
            elif row.get("type") == "queue-operation" and row.get("operation") == "enqueue":
                role = "user"
                content = row.get("content", "")
        if role not in {"user", "assistant"}:
            continue
        text = _content_text(content).strip()
        if not text:
            continue
        messages.append({"role": role, "text": redact_secrets(text) if redact else text})
    return {
        "key": item["key"],
        "provider": item["provider"],
        "session_id": item["session_id"],
        "timestamp": item.get("timestamp", ""),
        "title": item.get("title", ""),
        "messages": messages,
    }


def extract_history(manifest_path: Path, ids: Iterable[str], redact: bool = False) -> list[dict[str, Any]]:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    requested: set[str] = set()
    for raw in ids:
        requested.update(part.strip() for part in raw.split(",") if part.strip())
    selected = [
        item
        for item in manifest.get("eligible", [])
        if item.get("key") in requested or item.get("session_id") in requested
    ]
    return [_extract_session(item, redact) for item in selected]


def _decision_text(value: Any) -> str:
    return re.sub(r"\s+", " ", redact_secrets(str(value or ""))).strip()


def _decision_timestamp(value: str, fallback: str) -> str:
    candidate = value or fallback
    try:
        parsed = dt.datetime.fromisoformat(candidate.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return dt.datetime.now().astimezone().isoformat(timespec="seconds")
    return parsed.isoformat(timespec="seconds")


def _render_backfilled_workblock(
    decision: dict[str, Any],
    session_items: list[dict[str, Any]],
) -> str:
    timestamps = sorted(str(item.get("timestamp", "")) for item in session_items if item.get("timestamp"))
    created_fallback = timestamps[0][:10] if timestamps else dt.date.today().isoformat()
    updated_fallback = timestamps[-1] if timestamps else dt.datetime.now().astimezone().isoformat()
    created = str(decision.get("created") or created_fallback)
    updated = _decision_timestamp(str(decision.get("updated") or ""), updated_fallback)
    scope = _decision_text(decision.get("scope") or "general")
    yaml_scope = f'"{scope}"' if scope.startswith("[[") else scope
    status = str(decision.get("status") or "completed")
    confidence = str(decision.get("confidence") or "medium")
    key_files_raw = decision.get("key_files", [])
    if isinstance(key_files_raw, list):
        key_files = ", ".join(f"`{_decision_text(item)}`" for item in key_files_raw if _decision_text(item))
    else:
        key_files = _decision_text(key_files_raw)
    session_keys = [str(item["key"]) for item in session_items]
    return "\n".join(
        [
            "---",
            "type: workblock",
            f"status: {status}",
            f"scope: {yaml_scope}",
            f"created: {created}",
            f"updated: {updated}",
            "backfilled: true",
            f"confidence: {confidence}",
            "---",
            "",
            f"# {_decision_text(decision.get('scope_label') or scope)} — {_decision_text(decision.get('intent'))}",
            "",
            f"- Goal: {_decision_text(decision.get('goal'))}",
            f"- Current state: {_decision_text(decision.get('current_state'))}",
            f"- Next action: {_decision_text(decision.get('next_action'))}",
            f"- Blocker / decision: {_decision_text(decision.get('blocker'))}",
            f"- Key files: {key_files}",
            f"- Source sessions: {', '.join(session_keys)}",
            "",
        ]
    )


def _merge_sources_into_live(content: str, session_keys: Iterable[str]) -> str:
    normalized = content.replace("\r\n", "\n")
    match = re.search(r"^- Source sessions:\s*(.*)$", normalized, flags=re.MULTILINE)
    if not match:
        return normalized.rstrip() + f"\n- Source sessions: {', '.join(session_keys)}\n"
    current = [item.strip() for item in match.group(1).split(",") if item.strip()]
    combined = current + [key for key in session_keys if key not in current]
    replacement = f"- Source sessions: {', '.join(combined)}"
    return normalized[: match.start()] + replacement + normalized[match.end() :]


def _decision_session_keys(
    decision: dict[str, Any], eligible: list[dict[str, Any]]
) -> list[str]:
    keys = [str(key) for key in decision.get("sessions", [])]
    for raw_index in decision.get("indices", []):
        try:
            index = int(raw_index)
        except (TypeError, ValueError):
            continue
        if 1 <= index <= len(eligible):
            key = str(eligible[index - 1]["key"])
            if key not in keys:
                keys.append(key)
    return keys


def apply_backfill_decisions(
    manifest_path: Path,
    decisions_path: Path,
    workblocks_root: Path,
    *,
    batch_size: int = 20,
) -> dict[str, Any]:
    """Apply explicit semantic decisions and checkpoint coverage after each batch."""
    manifest_path = Path(manifest_path)
    decisions_path = Path(decisions_path)
    workblocks_root = Path(workblocks_root)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    eligible = manifest.get("eligible", [])
    eligible_by_key = {item["key"]: item for item in eligible}
    output_root = manifest_path.parent
    report_path = output_root / "report.json"
    try:
        prior_report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        prior_report = {}
    state_path = output_root / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {"version": 1, "manifest": manifest_path.name, "batch_size": batch_size, "sessions": {}}
    state["batch_size"] = batch_size
    state_sessions: dict[str, Any] = state.setdefault("sessions", {})

    groups_by_key: dict[str, dict[str, Any]] = {}
    duplicate_keys: set[str] = set()
    for decision in decisions.get("workblocks", []):
        for key in _decision_session_keys(decision, eligible):
            if key in groups_by_key:
                duplicate_keys.add(key)
            groups_by_key[key] = decision

    failures: list[dict[str, str]] = []
    created = 0
    updated = 0
    mapped = 0
    skipped = 0
    workblock_paths: dict[int, Path] = {}
    workblocks_root.mkdir(parents=True, exist_ok=True)
    existing_names = {path.name for path in workblocks_root.glob("*.md")}

    for decision in decisions.get("workblocks", []):
        intent = _decision_text(decision.get("intent"))
        scope_label = _decision_text(decision.get("scope_label") or decision.get("scope") or "General")
        session_keys = [
            key for key in _decision_session_keys(decision, eligible) if key in eligible_by_key
        ]
        if not intent or not session_keys:
            continue
        preferred_name = safe_filename(scope_label, intent, session_keys[0].split(":", 1)[-1], set())
        path = workblocks_root / preferred_name
        if path.name not in existing_names and not path.exists():
            collision_name = safe_filename(
                scope_label, intent, session_keys[0].split(":", 1)[-1], existing_names
            )
            path = workblocks_root / collision_name
        workblock_paths[id(decision)] = path
        items = [eligible_by_key[key] for key in session_keys]
        rendered = _render_backfilled_workblock(decision, items)
        if path.exists():
            current = path.read_text(encoding="utf-8-sig")
            metadata, _ = parse_frontmatter(current)
            if _as_bool(metadata.get("backfilled", "")) is False:
                desired = _merge_sources_into_live(current, session_keys)
            else:
                desired = rendered
            if current.replace("\r\n", "\n") != desired:
                atomic_write_text(path, desired)
                updated += 1
        else:
            atomic_write_text(path, rendered)
            existing_names.add(path.name)
            created += 1

    default = decisions.get("default", {"outcome": "skipped", "reason": "not_stateful"})
    for index, item in enumerate(eligible, start=1):
        key = item["key"]
        if key in duplicate_keys:
            failures.append({"key": key, "reason": "duplicate_decision"})
            state_sessions[key] = {"outcome": "failed", "reason": "duplicate_decision"}
        elif key in groups_by_key:
            decision = groups_by_key[key]
            path = workblock_paths.get(id(decision))
            if path is None:
                failures.append({"key": key, "reason": "invalid_workblock_decision"})
                state_sessions[key] = {"outcome": "failed", "reason": "invalid_workblock_decision"}
            else:
                mapped += 1
                state_sessions[key] = {
                    "outcome": "mapped",
                    "workblock": str(path),
                }
        elif default.get("outcome") == "skipped" and default.get("reason") == "not_stateful":
            skipped += 1
            state_sessions[key] = {"outcome": "skipped", "reason": "not_stateful"}
        else:
            failures.append({"key": key, "reason": "missing_decision"})
            state_sessions[key] = {"outcome": "failed", "reason": "missing_decision"}

        if index % batch_size == 0:
            atomic_write_json(state_path, state)
    atomic_write_json(state_path, state)

    merged = sum(
        max(
            0,
            len(
                [
                    key
                    for key in _decision_session_keys(decision, eligible)
                    if key in eligible_by_key
                ]
            )
            - 1,
        )
        for decision in decisions.get("workblocks", [])
    )
    created_total = int(prior_report.get("created_total", prior_report.get("created", 0))) + created
    updated_total = int(prior_report.get("updated_total", prior_report.get("updated", 0))) + updated
    report = {
        "scanned": int(manifest.get("counts", {}).get("scanned", len(eligible))),
        "excluded": int(manifest.get("counts", {}).get("excluded", 0)),
        "eligible": len(eligible),
        "mapped": mapped,
        "skipped": skipped,
        "merged": merged,
        "created": created_total,
        "updated": updated_total,
        "created_this_run": created,
        "updated_this_run": updated,
        "created_total": created_total,
        "updated_total": updated_total,
        "failed": len(failures),
        "coverage_ok": mapped + skipped + len(failures) == len(eligible),
        "failures": failures,
    }
    atomic_write_json(report_path, report)
    return report


def _jsonable_results(results: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**item, "path": str(item["path"])} for item in results]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage and validate vault workblocks.")
    parser.add_argument("--vault-root", type=Path, default=Path.cwd(), help="Vault root (default: cwd).")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List matching workblocks.")
    list_parser.add_argument("--statuses", default="active,blocked")
    list_parser.add_argument("--query", default="")
    list_parser.add_argument("--json", action="store_true")

    validate_parser = subparsers.add_parser("validate", help="Validate workblock files.")
    validate_parser.add_argument("--json", action="store_true")

    index_parser = subparsers.add_parser("index-history", help="Index eligible Claude and Codex sessions.")
    index_parser.add_argument("--vault-root", dest="index_vault_root", type=Path)
    index_parser.add_argument("--output", type=Path, required=True)
    index_parser.add_argument("--claude-root", type=Path)
    index_parser.add_argument("--codex-root", type=Path)
    index_parser.add_argument("--codex-index", type=Path)

    extract_parser = subparsers.add_parser("extract-history", help="Extract selected sessions from a manifest.")
    extract_parser.add_argument("--manifest", type=Path, required=True)
    extract_parser.add_argument("--ids", nargs="+", required=True)
    extract_parser.add_argument("--redact", action="store_true")

    apply_parser = subparsers.add_parser(
        "apply-history", help="Apply explicit backfill decisions with resumable checkpoints."
    )
    apply_parser.add_argument("--manifest", type=Path, required=True)
    apply_parser.add_argument("--decisions", type=Path, required=True)
    apply_parser.add_argument("--workblocks-root", type=Path, required=True)
    apply_parser.add_argument("--batch-size", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "list":
        statuses = {value.strip() for value in args.statuses.split(",") if value.strip()}
        invalid = statuses - STATUSES
        if invalid:
            print(f"Invalid statuses: {', '.join(sorted(invalid))}", file=sys.stderr)
            return 2
        results = find_workblocks(args.vault_root / "80_Workblocks", statuses, args.query)
        if args.json:
            print(json.dumps(_jsonable_results(results), indent=2, ensure_ascii=False))
        else:
            for item in results:
                print(f"{item['status']:9} {item['path']} — {item['heading']}")
        return 0
    if args.command == "validate":
        result = validate_workblocks(args.vault_root / "80_Workblocks")
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Checked {result['checked']} workblock(s).")
            for warning in result["warnings"]:
                print(f"WARNING {warning['path']}: {warning['message']}")
            for error in result["errors"]:
                print(f"ERROR {error['path']}: {error['message']}")
        return 1 if result["errors"] else 0
    if args.command == "index-history":
        vault_root = args.index_vault_root or args.vault_root
        manifest = index_history(
            vault_root,
            args.output,
            claude_root=args.claude_root,
            codex_root=args.codex_root,
            codex_index=args.codex_index,
        )
        print(json.dumps(manifest["counts"], indent=2, ensure_ascii=False))
        return 0
    if args.command == "extract-history":
        extracted = extract_history(args.manifest, args.ids, redact=args.redact)
        print(json.dumps(extracted, indent=2, ensure_ascii=False))
        return 0
    if args.command == "apply-history":
        report = apply_backfill_decisions(
            args.manifest,
            args.decisions,
            args.workblocks_root,
            batch_size=args.batch_size,
        )
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report["failed"] else 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
