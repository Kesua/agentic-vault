"""Meeting note metadata: project inference and Fireflies speakers.

Shared by gcal_today and fireflies_sync; also provides a local-only backfill:

    .\\.venv\\Scripts\\python.exe 90_System\\Skills\\meeting_metadata\\meeting_metadata.py backfill --from YYYY-MM-DD --to YYYY-MM-DD --dry-run

Rules
- `project:` = journal name (filename of 30_Projects/Journal/<Project>.md without .md), inferred from
  30_Projects/Journal/_project_map.json via attendee email domains and title keywords. Ambiguous or no
  signal -> left empty. A non-empty existing value is never overwritten. A missing or empty map means
  no project inference (speakers still work).
- Map schema: {"projects": {"<Journal name>": {"domains": [...], "title_keywords": [...],
  "slack_channels": [...]}}}; keys starting with "_" (e.g. "_about") are documentation and ignored.
- `speakers:` = de-duplicated speaker names from the Fireflies transcript, in order of first appearance.
  `attendees:` (calendar invite) is never touched.
- Edits touch only the frontmatter. Legacy blocks missing the closing (older gcal_today output) or opening `---` get the missing delimiter.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PROJECT_MAP_PATH = REPO_ROOT / "30_Projects" / "Journal" / "_project_map.json"
MEETINGS_DIR = REPO_ROOT / "20_Meetings"

EMAIL_RE = re.compile(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]")
FM_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):(.*)$")
TRANSCRIPT_HEADING_RE = re.compile(r"(?m)^##\s+Fireflies\s+Transcript\s+\(auto\)\s*$")
SPEAKER_LINE_RE = re.compile(r"^\[(?:\d{2}:\d{2}:\d{2}|\?\?:\?\?:\?\?)\]\s+(.+?):\s")
NOTE_NAME_RE = re.compile(r"^\d{4}\s+-\s+(?P<title>.+)\.md$", re.IGNORECASE)


# --------------------------------------------------------------------------- project map


@dataclass(frozen=True)
class ProjectRule:
    name: str
    domains: tuple[str, ...] = ()
    title_keywords: tuple[str, ...] = ()
    slack_channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProjectMatch:
    project: str  # "" when not inferred
    candidates: tuple[str, ...] = ()  # all projects that had any signal
    reason: str = "none"  # match | ambiguous | none


def load_project_map(path: Path = PROJECT_MAP_PATH) -> list[ProjectRule]:
    """Rules from the project map; a missing or empty file yields no rules (no project inference)."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8-sig").strip()
    data = json.loads(text) if text else {}
    rules: list[ProjectRule] = []
    for name, raw in (data.get("projects") or {}).items():
        if name.startswith("_"):
            continue
        raw = raw or {}
        rules.append(
            ProjectRule(
                name=name,
                domains=tuple(d.strip().lower().lstrip("@") for d in raw.get("domains") or [] if d.strip()),
                title_keywords=tuple(k for k in raw.get("title_keywords") or [] if k.strip()),
                slack_channels=tuple(c.strip().lstrip("#").lower() for c in raw.get("slack_channels") or [] if c.strip()),
            )
        )
    return rules


def strip_wikilinks(text: str) -> str:
    return WIKILINK_RE.sub(lambda m: m.group(2) if m.group(2) is not None else m.group(1), text or "")


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", strip_wikilinks(text)).casefold()
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", text).split())


def _title_matches(title: str, keyword: str) -> bool:
    kw = _normalize(keyword)
    return bool(kw) and f" {kw} " in f" {_normalize(title)} "


def email_domains(values: list[str] | tuple[str, ...]) -> set[str]:
    return {d.lower() for value in values for d in EMAIL_RE.findall(value or "")}


def _domain_matches(domain: str, rule_domain: str) -> bool:
    return domain == rule_domain or domain.endswith("." + rule_domain)


def infer_project(
    rules: list[ProjectRule],
    *,
    title: str = "",
    attendees: list[str] | tuple[str, ...] = (),
    slack_channel: str = "",
) -> ProjectMatch:
    """Title keywords (or a Slack channel) and attendee domains must agree on exactly one project."""
    domains = email_domains(attendees)
    by_domain = {r.name for r in rules if any(_domain_matches(d, rd) for d in domains for rd in r.domains)}
    by_title = {r.name for r in rules if any(_title_matches(title, kw) for kw in r.title_keywords)}
    channel = slack_channel.strip().lstrip("#").lower()
    if channel:
        by_title |= {r.name for r in rules if channel in r.slack_channels}

    if by_title:
        candidates = by_title & by_domain if by_domain else by_title
    else:
        candidates = by_domain
    signals = tuple(sorted(by_title | by_domain))
    if len(candidates) == 1:
        return ProjectMatch(next(iter(candidates)), signals, "match")
    if signals:
        return ProjectMatch("", signals, "ambiguous")
    return ProjectMatch("", (), "none")


# --------------------------------------------------------------------------- speakers


def dedupe_speakers(names: list[str | None]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in names:
        name = " ".join(strip_wikilinks(raw or "").split())
        if not name or name.casefold() == "unknown":
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def speakers_from_note(text: str) -> list[str]:
    """Speakers from an existing `## Fireflies Transcript (auto)` block (local content only)."""
    match = TRANSCRIPT_HEADING_RE.search(text)
    if not match:
        return []
    names: list[str] = []
    for line in text[match.end():].splitlines():
        if line.startswith("## "):
            break
        m = SPEAKER_LINE_RE.match(line)
        if m:
            names.append(m.group(1))
    return dedupe_speakers(names)


# --------------------------------------------------------------------------- frontmatter


@dataclass
class Frontmatter:
    lines: list[str]  # without delimiters and without line endings
    closed: bool  # False when a delimiter was missing (repaired on write)
    bom: str
    body: str  # text after the frontmatter (after closing --- when closed)
    newline: str = "\n"


def split_frontmatter(text: str) -> Frontmatter | None:
    bom = "﻿" if text.startswith("﻿") else ""
    raw = text[len(bom):]
    newline = "\r\n" if "\r\n" in raw[:200] else "\n"
    all_lines = raw.splitlines(keepends=True)
    if all_lines and all_lines[0].strip() == "---":
        start = 1
    else:
        # Legacy meeting note that lost its opening `---` (blank first line, then `type: meeting_note`).
        start = 0
        while start < len(all_lines) and not all_lines[start].strip():
            start += 1
        if start >= len(all_lines) or not re.match(r"^type:\s*meeting_note\s*$", all_lines[start].strip()):
            return None
    end = start
    while end < len(all_lines):
        line = all_lines[end].rstrip("\r\n")
        if line.strip() == "---":
            lines = [ln.rstrip("\r\n") for ln in all_lines[start:end]]
            return Frontmatter(lines, start == 1, bom, "".join(all_lines[end + 1:]), newline)
        if FM_KEY_RE.match(line) or re.match(r"^\s+\S", line) or not line.strip():
            end += 1
            continue
        break
    # Unclosed block (legacy gcal_today output): ends before the first line that is not YAML-like.
    while end > start and not all_lines[end - 1].strip():
        end -= 1
    if end == start:
        return None
    lines = [ln.rstrip("\r\n") for ln in all_lines[start:end]]
    return Frontmatter(lines, False, bom, "".join(all_lines[end:]), newline)


def join_frontmatter(fm: Frontmatter) -> str:
    nl = fm.newline
    return fm.bom + "---" + nl + "".join(line + nl for line in fm.lines) + "---" + nl + fm.body


def _key_span(lines: list[str], key: str) -> tuple[int, int] | None:
    for i, line in enumerate(lines):
        m = FM_KEY_RE.match(line)
        if m and m.group(1) == key:
            j = i + 1
            while j < len(lines) and re.match(r"^\s+\S", lines[j]):
                j += 1
            return i, j
    return None


def _unquote(value: str) -> str:
    value = value.strip()
    if value[:1] in ('"', "'"):
        quote = value[0]
        out, i = [], 1
        while i < len(value):
            ch = value[i]
            if quote == '"' and ch == "\\" and i + 1 < len(value):
                out.append(value[i + 1])
                i += 2
                continue
            if ch == quote:
                break
            out.append(ch)
            i += 1
        return "".join(out)
    return re.sub(r"\s+#.*$", "", value).strip()


def get_value(fm: Frontmatter, key: str) -> str | list[str] | None:
    span = _key_span(fm.lines, key)
    if span is None:
        return None
    start, end = span
    scalar = FM_KEY_RE.match(fm.lines[start]).group(2).strip()
    if scalar[:1] not in ('"', "'"):
        scalar = re.sub(r"(?:^|\s+)#.*$", "", scalar).strip()
    if scalar.startswith("[") and scalar.endswith("]") and not scalar.startswith("[["):
        inner = scalar[1:-1].strip()
        return [_unquote(v) for v in inner.split(",") if _unquote(v)] if inner else []
    if scalar:
        return _unquote(scalar)
    items = [_unquote(re.sub(r"^\s*-\s*", "", ln)) for ln in fm.lines[start + 1:end] if re.match(r"^\s*-", ln)]
    return [v for v in items if v]


def is_empty(value: str | list[str] | None) -> bool:
    if value is None:
        return True
    if isinstance(value, list):
        return not any(v.strip() for v in value)
    return not value.strip()


def yaml_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _set_lines(fm: Frontmatter, key: str, new_lines: list[str], after: tuple[str, ...]) -> None:
    span = _key_span(fm.lines, key)
    if span is not None:
        fm.lines[span[0]:span[1]] = new_lines
        return
    for anchor in after:
        anchor_span = _key_span(fm.lines, anchor)
        if anchor_span is not None:
            fm.lines[anchor_span[1]:anchor_span[1]] = new_lines
            return
    fm.lines.extend(new_lines)


def copy_key(src: Frontmatter, dst: Frontmatter, key: str, after: tuple[str, ...] = ()) -> bool:
    """Copy `key` (with its list items) verbatim from src to dst; False when src lacks the key."""
    span = _key_span(src.lines, key)
    if span is None:
        return False
    _set_lines(dst, key, src.lines[span[0]:span[1]], after=after)
    return True


def set_project(fm: Frontmatter, project: str) -> None:
    _set_lines(fm, "project", [f"project: {yaml_quote(project)}"], after=("meeting_title", "date"))


def set_speakers(fm: Frontmatter, speakers: list[str]) -> None:
    block = ["speakers:"] + [f"  - {yaml_quote(s)}" for s in speakers] if speakers else ["speakers: []"]
    _set_lines(fm, "speakers", block, after=("attendees", "project"))


def note_title(fm: Frontmatter | None, path: Path | None = None) -> str:
    value = get_value(fm, "meeting_title") if fm else None
    if isinstance(value, str) and value.strip():
        return strip_wikilinks(value)
    if path is not None:
        m = NOTE_NAME_RE.match(path.name)
        if m:
            return m.group("title")
    return ""


@dataclass
class MetadataResult:
    text: str
    changed: bool
    project: str = ""
    project_status: str = "none"  # kept | set | ambiguous | none
    candidates: tuple[str, ...] = ()
    speakers: list[str] = field(default_factory=list)
    speakers_changed: bool = False
    repaired_frontmatter: bool = False
    has_frontmatter: bool = True


def apply_metadata(
    text: str,
    rules: list[ProjectRule],
    *,
    speakers: list[str] | None = None,
    path: Path | None = None,
) -> MetadataResult:
    """Fill `project` (only when empty) and `speakers` (when given) in the note frontmatter."""
    fm = split_frontmatter(text)
    if fm is None:
        return MetadataResult(text, False, has_frontmatter=False)

    result = MetadataResult(text, False)
    current = get_value(fm, "project")
    if not is_empty(current):
        result.project = current if isinstance(current, str) else ", ".join(current)
        result.project_status = "kept"
    else:
        attendees = get_value(fm, "attendees")
        attendees = attendees if isinstance(attendees, list) else [attendees or ""]
        match = infer_project(rules, title=note_title(fm, path), attendees=attendees)
        result.candidates = match.candidates
        result.project_status = "set" if match.project else match.reason
        if match.project:
            result.project = match.project
            set_project(fm, match.project)

    if speakers:
        speakers = dedupe_speakers(speakers)
        existing = get_value(fm, "speakers")
        if existing != speakers:
            set_speakers(fm, speakers)
            result.speakers_changed = True
        result.speakers = speakers

    new_text = join_frontmatter(fm)
    result.repaired_frontmatter = not fm.closed
    result.changed = new_text != text
    result.text = new_text if result.changed else text
    return result


# --------------------------------------------------------------------------- backfill


def iter_note_paths(meetings_dir: Path, from_day: date, to_day: date) -> list[Path]:
    out: list[Path] = []
    for path in sorted(meetings_dir.glob("[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]/*.md")):
        try:
            day = date(int(path.parent.parent.parent.name), int(path.parent.parent.name), int(path.parent.name))
        except ValueError:
            continue
        if from_day <= day <= to_day:
            out.append(path)
    return out


def backfill(meetings_dir: Path, from_day: date, to_day: date, rules: list[ProjectRule], dry_run: bool) -> dict:
    stats = {"scanned": 0, "changed": 0, "project_set": 0, "project_kept": 0, "project_ambiguous": 0,
             "project_none": 0, "speakers_set": 0, "frontmatter_repaired": 0, "no_frontmatter": 0}
    examples: list[tuple[str, str, int]] = []
    ambiguous: list[tuple[str, tuple[str, ...]]] = []
    no_frontmatter: list[str] = []
    for path in iter_note_paths(meetings_dir, from_day, to_day):
        stats["scanned"] += 1
        with path.open(encoding="utf-8", errors="replace", newline="") as handle:  # keep CRLF/LF as-is
            text = handle.read()
        result = apply_metadata(text, rules, speakers=speakers_from_note(text), path=path)
        rel = path.relative_to(meetings_dir).as_posix()
        if not result.has_frontmatter:
            stats["no_frontmatter"] += 1
            no_frontmatter.append(rel)
            continue
        stats[f"project_{result.project_status}"] += 1
        if result.project_status == "ambiguous":
            ambiguous.append((rel, result.candidates))
        if result.speakers_changed:
            stats["speakers_set"] += 1
        if result.changed:
            stats["changed"] += 1
            if result.repaired_frontmatter:
                stats["frontmatter_repaired"] += 1
            if result.project_status == "set" or result.speakers_changed:
                examples.append((rel, result.project, len(result.speakers)))
            if not dry_run:
                path.write_text(result.text, encoding="utf-8", newline="")
    return {"stats": stats, "examples": examples, "ambiguous": ambiguous, "no_frontmatter": no_frontmatter}


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    parser = argparse.ArgumentParser(prog="meeting_metadata")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("backfill", help="Fill project/speakers in existing meeting notes from local content only")
    p.add_argument("--from", dest="from_day", required=True, help="YYYY-MM-DD (folder date)")
    p.add_argument("--to", dest="to_day", required=True, help="YYYY-MM-DD (folder date, inclusive)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--meetings-dir", default=str(MEETINGS_DIR), help="Root with YYYY/MM/DD folders (default: 20_Meetings)")
    p.add_argument("--project-map", default=str(PROJECT_MAP_PATH))
    p.add_argument("--limit", type=int, default=25, help="Max listed examples/ambiguous notes")
    args = parser.parse_args(argv)

    from_day, to_day = date.fromisoformat(args.from_day), date.fromisoformat(args.to_day)
    if to_day < from_day:
        raise ValueError("--to must be >= --from")
    report = backfill(Path(args.meetings_dir), from_day, to_day, load_project_map(Path(args.project_map)), args.dry_run)
    print(f"Window: {from_day} .. {to_day}{' (dry run)' if args.dry_run else ''}")
    for key, value in report["stats"].items():
        print(f"{key}: {value}")
    print("Examples:")
    for rel, project, n in report["examples"][: args.limit]:
        print(f"  ~ {rel} | project={project or '-'} | speakers={n}")
    print("Ambiguous project:")
    for rel, candidates in report["ambiguous"][: args.limit]:
        print(f"  ? {rel} | {', '.join(candidates)}")
    if report["no_frontmatter"]:
        print("Skipped (no frontmatter):")
        for rel in report["no_frontmatter"][: args.limit]:
            print(f"  ! {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
