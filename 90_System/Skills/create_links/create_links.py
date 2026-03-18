from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

ENTITY_SOURCE_DIRS = {
    "person": REPO_ROOT / "40_People",
    "project": REPO_ROOT / "30_Projects",
    "area": REPO_ROOT / "50_Areas",
}
TARGET_DIRS = [
    REPO_ROOT / "00_Mailbox",
    REPO_ROOT / "10_DailyBriefs",
    REPO_ROOT / "20_Meetings",
    REPO_ROOT / "30_Projects",
    REPO_ROOT / "50_Areas",
]

KEY_VALUE_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
URL_RE = re.compile(r"(?:[A-Za-z][A-Za-z0-9+.-]*://|mailto:)\S+")


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
class AliasTarget:
    alias_text: str
    target_type: str
    target_link_path: str
    source_file: str

    @property
    def wikilink(self) -> str:
        return f"[[{self.target_link_path}|{self.alias_text}]]"


@dataclass(frozen=True)
class FileChange:
    path: Path
    replacements: int


class AliasMatcher:
    def __init__(self, registry: dict[str, AliasTarget]) -> None:
        self._registry = registry
        aliases = sorted(registry, key=lambda value: (-len(value), value))
        self._pattern = re.compile("|".join(re.escape(alias) for alias in aliases)) if aliases else None

    @property
    def alias_count(self) -> int:
        return len(self._registry)

    def replace(self, text: str) -> tuple[str, int]:
        if not text or self._pattern is None:
            return text, 0

        parts: list[str] = []
        last_index = 0
        replacements = 0

        for match in self._pattern.finditer(text):
            start, end = match.span()
            if not _has_token_boundaries(text, start, end):
                continue

            alias_text = match.group(0)
            target = self._registry[alias_text]
            parts.append(text[last_index:start])
            parts.append(target.wikilink)
            last_index = end
            replacements += 1

        if replacements == 0:
            return text, 0

        parts.append(text[last_index:])
        return "".join(parts), replacements


def _has_token_boundaries(text: str, start: int, end: int) -> bool:
    if start > 0 and text[start - 1].isalnum():
        return False
    if end < len(text) and text[end].isalnum():
        return False
    return True


def _iter_markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(
        (path for path in root.rglob("*.md") if path.is_file() and not _is_within_submodule(path)),
        key=lambda path: path.as_posix().lower(),
    )


def _find_nearest_git_root(path: Path) -> Path | None:
    for candidate in (path if path.is_dir() else path.parent, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _is_within_submodule(path: Path) -> bool:
    git_root = _find_nearest_git_root(path)
    return git_root is not None and git_root != REPO_ROOT


def _split_leading_metadata(text: str) -> tuple[str, str]:
    bom = ""
    if text.startswith("\ufeff"):
        bom = "\ufeff"
        text = text[1:]

    if not text.startswith("---\n") and text != "---":
        return "", bom + text

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return "", bom + text

    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            metadata = bom + "".join(lines[: index + 1])
            body = "".join(lines[index + 1 :])
            return metadata, body

    if len(lines) < 2 or not _looks_like_yaml_line(lines[1]):
        return "", bom + text

    end_index = 1
    while end_index < len(lines) and _looks_like_yaml_line(lines[end_index]):
        end_index += 1

    metadata = bom + "".join(lines[:end_index])
    body = "".join(lines[end_index:])
    return metadata, body


def _looks_like_yaml_line(line: str) -> bool:
    stripped = line.rstrip("\n").rstrip("\r")
    if not stripped.strip():
        return True
    if stripped.lstrip().startswith("#"):
        return True
    if re.match(r"^\s*-\s+.+$", stripped):
        return True
    return bool(KEY_VALUE_RE.match(stripped))


def _parse_metadata_block(metadata_block: str) -> dict[str, object]:
    if not metadata_block:
        return {}

    text = metadata_block.lstrip("\ufeff")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    start_index = 1
    end_index = len(lines)
    if end_index > start_index and lines[-1].strip() == "---":
        end_index -= 1

    data: dict[str, object] = {}
    index = start_index
    while index < end_index:
        raw_line = lines[index]
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue

        if line.startswith(" ") or line.startswith("\t"):
            index += 1
            continue

        match = KEY_VALUE_RE.match(line)
        if not match:
            index += 1
            continue

        key = match.group(1)
        raw_value = match.group(2).strip()
        if raw_value:
            data[key] = _parse_scalar_or_list(raw_value)
            index += 1
            continue

        items: list[object] = []
        list_index = index + 1
        while list_index < end_index:
            list_line = lines[list_index].rstrip()
            if not list_line.strip():
                list_index += 1
                continue
            list_match = re.match(r"^\s*-\s+(.*)$", list_line)
            if not list_match:
                break
            items.append(_parse_scalar_or_list(list_match.group(1).strip()))
            list_index += 1

        data[key] = items
        index = list_index

    return data


def _parse_scalar_or_list(raw_value: str) -> object:
    raw_value = _strip_inline_comment(raw_value).strip()
    if not raw_value:
        return ""

    if raw_value.startswith("[") and raw_value.endswith("]"):
        inner = raw_value[1:-1].strip()
        if not inner:
            return []
        return [_parse_scalar_or_list(part) for part in _split_inline_list(inner)]

    return _unquote_scalar(raw_value)


def _strip_inline_comment(raw_value: str) -> str:
    in_single = False
    in_double = False
    escaped = False

    for index, char in enumerate(raw_value):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_double:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if char == "#" and not in_single and not in_double:
            if index == 0 or raw_value[index - 1].isspace():
                return raw_value[:index].rstrip()

    return raw_value


def _split_inline_list(text: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    in_single = False
    in_double = False
    escaped = False

    for char in text:
        if escaped:
            current.append(char)
            escaped = False
            continue
        if char == "\\" and in_double:
            current.append(char)
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            current.append(char)
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            current.append(char)
            continue
        if char == "," and not in_single and not in_double:
            part = "".join(current).strip()
            if part:
                items.append(part)
            current = []
            continue
        current.append(char)

    part = "".join(current).strip()
    if part:
        items.append(part)
    return items


def _unquote_scalar(raw_value: str) -> str:
    if len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in ("'", '"'):
        quote = raw_value[0]
        inner = raw_value[1:-1]
        if quote == '"':
            inner = inner.replace("\\\\", "\\").replace('\\"', '"')
        return inner
    return raw_value


def _build_alias_registry() -> tuple[dict[str, AliasTarget], dict[str, list[AliasTarget]]]:
    alias_map: dict[str, list[AliasTarget]] = defaultdict(list)

    for expected_type, root in ENTITY_SOURCE_DIRS.items():
        for path in _iter_markdown_files(root):
            text = path.read_text(encoding="utf-8", errors="replace")
            metadata_block, _ = _split_leading_metadata(text)
            metadata = _parse_metadata_block(metadata_block)
            entity_type = str(metadata.get("type") or "").strip()
            if entity_type != expected_type:
                continue

            aliases = metadata.get("aliases")
            if not isinstance(aliases, list):
                continue

            relative_path = path.relative_to(REPO_ROOT)
            target_link_path = (
                path.stem if expected_type == "person" else relative_path.with_suffix("").as_posix()
            )
            source_file = relative_path.as_posix()

            seen_aliases: set[str] = set()
            for alias in aliases:
                alias_text = str(alias).strip()
                if not alias_text or alias_text in seen_aliases:
                    continue
                seen_aliases.add(alias_text)
                alias_map[alias_text].append(
                    AliasTarget(
                        alias_text=alias_text,
                        target_type=expected_type,
                        target_link_path=target_link_path,
                        source_file=source_file,
                    )
                )

    registry: dict[str, AliasTarget] = {}
    ambiguous: dict[str, list[AliasTarget]] = {}
    for alias_text, targets in alias_map.items():
        unique_targets = {
            (target.target_type, target.target_link_path, target.source_file): target for target in targets
        }
        if len(unique_targets) == 1:
            registry[alias_text] = next(iter(unique_targets.values()))
        else:
            ambiguous[alias_text] = list(unique_targets.values())

    return registry, ambiguous


def _is_line_start(text: str, index: int) -> bool:
    return index == 0 or text[index - 1] == "\n"


def _consume_fenced_code(text: str, index: int) -> int | None:
    if not _is_line_start(text, index):
        return None

    fence_start = index
    while fence_start < len(text) and fence_start - index < 3 and text[fence_start] == " ":
        fence_start += 1

    if fence_start >= len(text):
        return None

    fence_char = text[fence_start]
    if fence_char not in ("`", "~"):
        return None

    fence_len = 0
    while fence_start + fence_len < len(text) and text[fence_start + fence_len] == fence_char:
        fence_len += 1

    if fence_len < 3:
        return None

    line_end = text.find("\n", fence_start)
    search_index = len(text) if line_end == -1 else line_end + 1

    while search_index < len(text):
        candidate = search_index
        while candidate < len(text) and candidate - search_index < 3 and text[candidate] == " ":
            candidate += 1

        if text.startswith(fence_char * fence_len, candidate):
            close_end = candidate + fence_len
            while close_end < len(text) and text[close_end] == fence_char:
                close_end += 1
            newline_index = text.find("\n", close_end)
            return len(text) if newline_index == -1 else newline_index + 1

        newline_index = text.find("\n", search_index)
        if newline_index == -1:
            break
        search_index = newline_index + 1

    return len(text)


def _consume_wikilink(text: str, index: int) -> int | None:
    if not text.startswith("[[", index):
        return None
    end_index = text.find("]]", index + 2)
    if end_index == -1:
        return None
    return end_index + 2


def _consume_markdown_link(text: str, index: int) -> int | None:
    if text.startswith("![", index):
        end_index = _consume_markdown_link_from_bracket(text, index + 1)
        return end_index
    if text.startswith("[[", index) or index >= len(text) or text[index] != "[":
        return None
    return _consume_markdown_link_from_bracket(text, index)


def _consume_markdown_link_from_bracket(text: str, bracket_index: int) -> int | None:
    cursor = bracket_index + 1
    depth = 1

    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "[":
            depth += 1
            cursor += 1
            continue
        if char == "]":
            depth -= 1
            cursor += 1
            if depth == 0:
                break
            continue
        cursor += 1

    if depth != 0:
        return None

    while cursor < len(text) and text[cursor] in (" ", "\t"):
        cursor += 1
    if cursor >= len(text) or text[cursor] != "(":
        return None

    cursor += 1
    depth = 1
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            cursor += 2
            continue
        if char == "(":
            depth += 1
            cursor += 1
            continue
        if char == ")":
            depth -= 1
            cursor += 1
            if depth == 0:
                return cursor
            continue
        cursor += 1

    return None


def _consume_inline_code(text: str, index: int) -> int | None:
    if index >= len(text) or text[index] != "`":
        return None

    fence_len = 1
    while index + fence_len < len(text) and text[index + fence_len] == "`":
        fence_len += 1

    delimiter = "`" * fence_len
    end_index = text.find(delimiter, index + fence_len)
    if end_index == -1:
        return None
    return end_index + fence_len


def _consume_url(text: str, index: int) -> int | None:
    match = URL_RE.match(text, index)
    if not match:
        return None
    return match.end()


def _consume_protected_span(text: str, index: int) -> int | None:
    for consumer in (
        _consume_fenced_code,
        _consume_markdown_link,
        _consume_wikilink,
        _consume_inline_code,
        _consume_url,
    ):
        end_index = consumer(text, index)
        if end_index is not None and end_index > index:
            return end_index
    return None


def _rewrite_body(text: str, matcher: AliasMatcher) -> tuple[str, int]:
    if not text or matcher.alias_count == 0:
        return text, 0

    parts: list[str] = []
    replacements = 0
    plain_start = 0
    index = 0

    while index < len(text):
        protected_end = _consume_protected_span(text, index)
        if protected_end is None:
            index += 1
            continue

        if plain_start < index:
            rewritten, count = matcher.replace(text[plain_start:index])
            parts.append(rewritten)
            replacements += count

        parts.append(text[index:protected_end])
        index = protected_end
        plain_start = index

    if not parts:
        return matcher.replace(text)

    if plain_start < len(text):
        rewritten, count = matcher.replace(text[plain_start:])
        parts.append(rewritten)
        replacements += count

    return "".join(parts), replacements


def sync_links(dry_run: bool) -> int:
    registry, ambiguous = _build_alias_registry()
    matcher = AliasMatcher(registry)

    files_scanned = 0
    files_skipped_entity_notes = 0
    files_skipped_submodules = 0
    changed_files: list[FileChange] = []
    replacements_made = 0

    for root in TARGET_DIRS:
        all_markdown_files = sorted((path for path in root.rglob("*.md") if path.is_file()), key=lambda path: path.as_posix().lower())
        files_skipped_submodules += sum(1 for path in all_markdown_files if _is_within_submodule(path))

        for path in _iter_markdown_files(root):
            files_scanned += 1

            text = path.read_text(encoding="utf-8", errors="replace")
            metadata_block, body = _split_leading_metadata(text)
            metadata = _parse_metadata_block(metadata_block)
            file_type = str(metadata.get("type") or "").strip()
            if file_type in {"person", "project", "area"}:
                files_skipped_entity_notes += 1
                continue

            rewritten_body, replacements = _rewrite_body(body, matcher)
            if replacements == 0:
                continue

            updated_text = metadata_block + rewritten_body
            if updated_text == text:
                continue

            if not dry_run:
                path.write_text(updated_text, encoding="utf-8")

            changed_files.append(FileChange(path=path, replacements=replacements))
            replacements_made += replacements

    mode_label = "dry-run" if dry_run else "write"
    change_label = "Files that would change" if dry_run else "Files changed"

    print(f"Mode: {mode_label}")
    print(f"Active aliases: {matcher.alias_count}")
    print(f"Files scanned: {files_scanned}")
    print(f"{change_label}: {len(changed_files)}")
    print(f"Replacements made: {replacements_made}")
    print(f"Ambiguous aliases skipped: {len(ambiguous)}")
    print(f"Files skipped (entity notes): {files_skipped_entity_notes}")
    print(f"Files skipped (submodules): {files_skipped_submodules}")

    for change in changed_files[:25]:
        rel_path = change.path.relative_to(REPO_ROOT).as_posix()
        print(f"  ~ {rel_path} ({change.replacements})")
    if len(changed_files) > 25:
        print("  ...")

    if ambiguous:
        for alias_text in sorted(ambiguous)[:25]:
            sources = ", ".join(sorted(target.source_file for target in ambiguous[alias_text]))
            print(f"  ! {alias_text}: {sources}")
        if len(ambiguous) > 25:
            print("  ...")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="create_links")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    sync_parser = subparsers.add_parser(
        "sync",
        help="Create Obsidian links for exact person/project/area aliases",
    )
    sync_parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")

    args = parser.parse_args(argv)

    if args.cmd == "sync":
        return sync_links(dry_run=bool(args.dry_run))

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
