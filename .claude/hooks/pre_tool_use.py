from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_ROOT = REPO_ROOT / "70_Exports"
BLOCKED_SEGMENTS = {
    ".git",
    ".venv",
    ".obsidian",
    "_attachments",
    "OneNoteNotes",
}
BLOCKED_PREFIXES = [
    REPO_ROOT / "90_System" / "secrets",
]


def _load_payload() -> dict:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _collect_paths(tool_name: str, tool_input: dict) -> list[Path]:
    candidates: list[str] = []
    if tool_name == "Write":
        candidates.extend([tool_input.get("file_path"), tool_input.get("path")])
    elif tool_name in {"Edit", "MultiEdit"}:
        candidates.extend([tool_input.get("file_path"), tool_input.get("path")])
    return [Path(candidate) for candidate in candidates if candidate]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _is_external_source_edit(path: Path) -> bool:
    if _is_within(path, REPO_ROOT):
        return False
    if _is_within(path, EXPORT_ROOT):
        return False
    return bool(re.search(r"\.(docx|pdf|xlsx|csv|tsv)$", path.name, flags=re.IGNORECASE))


def _blocked_reason(path: Path) -> str | None:
    normalized = path.resolve()

    for prefix in BLOCKED_PREFIXES:
        if _is_within(normalized, prefix):
            return f"Blocked path: {path}"

    if _is_within(normalized, REPO_ROOT):
        rel = normalized.relative_to(REPO_ROOT.resolve())
        if rel.parts and rel.parts[0] in BLOCKED_SEGMENTS:
            return f"Blocked path: {path}"

    if _is_external_source_edit(normalized):
        return (
            "External source files must not be edited in place. "
            "Copy them under 70_Exports/YYYY/MM/DD/ and edit only the exported copy."
        )

    return None


def main() -> int:
    payload = _load_payload()
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    for path in _collect_paths(tool_name, tool_input):
        reason = _blocked_reason(path)
        if reason:
            print(reason, file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
