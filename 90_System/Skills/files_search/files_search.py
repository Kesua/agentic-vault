from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterator


DEFAULT_LIMIT = 200
DEFAULT_CONTEXT = 60
TEXT_EXTENSIONS = {
    ".bat",
    ".bicep",
    ".c",
    ".cfg",
    ".cmd",
    ".conf",
    ".cpp",
    ".cs",
    ".css",
    ".csv",
    ".env",
    ".gitignore",
    ".go",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mjs",
    ".ps1",
    ".py",
    ".rb",
    ".rs",
    ".sh",
    ".sql",
    ".tex",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
}


def _resolve_existing_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Path does not exist: {path}")
    return path


def _normalize_ext(value: str) -> str:
    return value if value.startswith(".") else f".{value}"


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts if part not in (path.anchor, ""))


def _matches_type(path: Path, wanted: str) -> bool:
    if wanted == "all":
        return True
    if wanted == "file":
        return path.is_file()
    if wanted == "dir":
        return path.is_dir()
    raise ValueError(f"Unsupported type filter: {wanted}")


def _iter_children(base: Path, recursive: bool, max_depth: int | None, include_hidden: bool) -> Iterator[Path]:
    stack: list[tuple[Path, int]] = [(base, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            entries = sorted(current.iterdir(), key=lambda entry: entry.name.casefold())
        except (OSError, PermissionError):
            continue
        for entry in entries:
            relative = entry.relative_to(base)
            if not include_hidden and _is_hidden(relative):
                continue
            yield entry
            next_depth = depth + 1
            if entry.is_dir() and recursive and (max_depth is None or next_depth <= max_depth):
                stack.append((entry, next_depth))


def _iter_search_targets(base: Path, recursive: bool, max_depth: int | None, include_hidden: bool) -> Iterator[Path]:
    if base.is_file():
        if include_hidden or not _is_hidden(Path(base.name)):
            yield base
        return
    for entry in _iter_children(base, recursive, max_depth, include_hidden):
        yield entry


def _format_path(base: Path, target: Path) -> str:
    if base.is_file():
        return str(target)
    return os.fspath(target.relative_to(base))


def _print_payload(payload: Any, as_json: bool) -> None:
    if as_json:
        _write_line(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                _write_line(json.dumps(item, ensure_ascii=False))
            else:
                _write_line(str(item))
        return
    _write_line(str(payload))


def _write_line(text: str) -> None:
    encoding = sys.stdout.encoding or "utf-8"
    safe_text = text.encode(encoding, errors="backslashreplace").decode(encoding, errors="strict")
    sys.stdout.write(safe_text + os.linesep)


def command_list(args: argparse.Namespace) -> None:
    base = _resolve_existing_path(args.path)
    if not base.is_dir():
        raise NotADirectoryError(f"list expects a directory path: {base}")
    rows: list[dict[str, Any]] = []
    for entry in _iter_children(base, args.recursive, args.max_depth, args.include_hidden):
        if not _matches_type(entry, args.type):
            continue
        rows.append(
            {
                "path": _format_path(base, entry),
                "kind": "dir" if entry.is_dir() else "file",
            }
        )
        if len(rows) >= args.limit:
            break
    if args.json:
        _print_payload(rows, as_json=True)
        return
    _print_payload([row["path"] for row in rows], as_json=False)


def _matches_find_filters(path: Path, names: list[str], globs: list[str], exts: list[str]) -> bool:
    if names and path.name not in names:
        return False
    if globs and not any(fnmatch.fnmatch(path.name, pattern) or fnmatch.fnmatch(path.as_posix(), pattern) for pattern in globs):
        return False
    if exts and path.suffix.casefold() not in exts:
        return False
    return True


def command_find(args: argparse.Namespace) -> None:
    if not args.name and not args.glob and not args.ext:
        raise ValueError("find requires at least one of --name, --glob, or --ext")
    base = _resolve_existing_path(args.path)
    names = args.name or []
    globs = args.glob or []
    exts = [_normalize_ext(ext).casefold() for ext in (args.ext or [])]
    rows: list[dict[str, Any]] = []
    targets = [base] if base.is_file() else list(_iter_search_targets(base, args.recursive, args.max_depth, args.include_hidden))
    for target in sorted(targets, key=lambda item: str(item).casefold()):
        if not _matches_type(target, args.type):
            continue
        if not _matches_find_filters(target, names, globs, exts):
            continue
        rows.append(
            {
                "path": _format_path(base, target),
                "kind": "dir" if target.is_dir() else "file",
            }
        )
        if len(rows) >= args.limit:
            break
    if args.json:
        _print_payload(rows, as_json=True)
        return
    _print_payload([row["path"] for row in rows], as_json=False)


def _is_probably_text(path: Path) -> bool:
    if path.suffix.casefold() in TEXT_EXTENSIONS:
        return True
    try:
        with path.open("rb") as handle:
            sample = handle.read(4096)
    except (OSError, PermissionError):
        return False
    if b"\x00" in sample:
        return False
    return True


def _iter_text_files(base: Path, recursive: bool, max_depth: int | None, include_hidden: bool) -> Iterator[Path]:
    targets = [base] if base.is_file() else _iter_search_targets(base, recursive, max_depth, include_hidden)
    for target in targets:
        if not target.is_file():
            continue
        if _is_probably_text(target):
            yield target


def _excerpt(line: str, start: int, end: int, context: int) -> str:
    left = max(0, start - context)
    right = min(len(line), end + context)
    return line[left:right].strip()


def command_search_text(args: argparse.Namespace) -> None:
    base = _resolve_existing_path(args.path)
    query = args.query if args.case_sensitive else args.query.casefold()
    rows: list[dict[str, Any]] = []
    allowed_exts = {_normalize_ext(ext).casefold() for ext in (args.ext or [])}
    globs = args.glob or []

    for text_file in sorted(_iter_text_files(base, args.recursive, args.max_depth, args.include_hidden), key=lambda item: str(item).casefold()):
        if allowed_exts and text_file.suffix.casefold() not in allowed_exts:
            continue
        if globs and not any(fnmatch.fnmatch(text_file.name, pattern) or fnmatch.fnmatch(text_file.as_posix(), pattern) for pattern in globs):
            continue
        try:
            with text_file.open("r", encoding="utf-8-sig", errors="strict") as handle:
                for line_number, raw_line in enumerate(handle, start=1):
                    line = raw_line.rstrip("\n")
                    haystack = line if args.case_sensitive else line.casefold()
                    index = haystack.find(query)
                    if index == -1:
                        continue
                    rows.append(
                        {
                            "path": _format_path(base, text_file),
                            "line": line_number,
                            "excerpt": _excerpt(line, index, index + len(args.query), args.context),
                        }
                    )
                    if len(rows) >= args.limit:
                        break
        except (OSError, PermissionError, UnicodeDecodeError):
            continue
        if len(rows) >= args.limit:
            break

    if args.json:
        _print_payload(rows, as_json=True)
        return
    _print_payload([f"{row['path']}:{row['line']}: {row['excerpt']}" for row in rows], as_json=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="files_search",
        description="Read-only filesystem listing and search with explicit caller-passed paths.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--path", required=True, help="Absolute or relative path to inspect")
    common.add_argument("--include-hidden", action="store_true")
    common.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    common.add_argument("--json", action="store_true")

    walk = argparse.ArgumentParser(add_help=False)
    walk.add_argument("--recursive", action="store_true")
    walk.add_argument("--max-depth", type=int)

    type_filter = argparse.ArgumentParser(add_help=False)
    type_filter.add_argument("--type", choices=["file", "dir", "all"], default="all")

    p_list = sub.add_parser("list", parents=[common, walk, type_filter], help="List entries under a directory")
    p_list.set_defaults(func=command_list)

    p_find = sub.add_parser("find", parents=[common, walk, type_filter], help="Find paths by name, glob, or extension")
    p_find.add_argument("--name", action="append")
    p_find.add_argument("--glob", action="append")
    p_find.add_argument("--ext", action="append")
    p_find.set_defaults(func=command_find)

    p_search = sub.add_parser("search-text", parents=[common, walk], help="Search inside text files")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--glob", action="append")
    p_search.add_argument("--ext", action="append")
    p_search.add_argument("--case-sensitive", action="store_true")
    p_search.add_argument("--context", type=int, default=DEFAULT_CONTEXT)
    p_search.set_defaults(func=command_search_text)

    args = parser.parse_args(argv)
    if args.limit <= 0:
        raise ValueError("--limit must be a positive integer")
    if getattr(args, "max_depth", None) is not None and args.max_depth < 0:
        raise ValueError("--max-depth must be zero or greater")
    if getattr(args, "context", None) is not None and args.context < 0:
        raise ValueError("--context must be zero or greater")
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
