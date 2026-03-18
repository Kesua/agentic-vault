from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MEETINGS_DIR = REPO_ROOT / "20_Meetings"
MAILBOX_DIR = REPO_ROOT / "00_Mailbox"
PEOPLE_DIR = REPO_ROOT / "40_People"
PEOPLE_INDEX_PATH = PEOPLE_DIR / "_PeopleIndex.md"
PERSON_TEMPLATE_PATH = PEOPLE_DIR / "Templates" / "person_TEMPLATE.md"

KEY_VALUE_RE = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")


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


@dataclass
class AttendeeRecord:
    raw_value: str
    name: str
    emails: list[str]
    aliases: list[str]
    last_touch: str


@dataclass
class PersonNote:
    path: Path
    title: str
    metadata: dict[str, object]
    body: str


def _iter_markdown_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("*.md") if path.is_file())


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

    return "", bom + text


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
        line = lines[index].rstrip()
        if not line.strip() or line.lstrip().startswith("#") or line.startswith((" ", "\t")):
            index += 1
            continue

        match = KEY_VALUE_RE.match(line)
        if not match:
            index += 1
            continue

        key = match.group(1)
        raw_value = match.group(2).strip()
        if raw_value:
            data[key] = _unquote_scalar(raw_value)
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
            items.append(_unquote_scalar(list_match.group(1).strip()))
            list_index += 1

        data[key] = items
        index = list_index

    return data


def _unquote_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        inner = value[1:-1]
        if value[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return value


def _yaml_quote(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _sanitize_filename(text: str) -> str:
    text = re.sub(r'[<>:"/\\|?*]+', "-", text.strip())
    text = re.sub(r"\s+", " ", text).strip().rstrip(".")
    return text[:120] if text else "Unknown Person"


def _ensure_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _find_title(body: str, fallback: str) -> str:
    match = re.search(r"(?m)^#\s+(.+?)\s*$", body)
    return match.group(1).strip() if match else fallback


def _slug_aliases_from_email(email: str) -> list[str]:
    local = email.split("@", 1)[0].strip()
    local = local.split("+", 1)[0]
    if not local:
        return []
    if "." in local or " " in local:
        return [local]
    return []


def _is_safe_auto_alias(value: str) -> bool:
    alias = value.strip()
    if not alias:
        return False
    if "@" in alias:
        return True
    return "." in alias or " " in alias


def _filter_auto_aliases(values: list[str]) -> list[str]:
    return _dedupe_preserve_order([value for value in values if _is_safe_auto_alias(value)])


def _title_from_email(email: str) -> str:
    local = email.split("@", 1)[0].strip().split("+", 1)[0]
    tokens = [token for token in re.split(r"[._-]+", local) if token]
    if not tokens:
        return email
    return " ".join(token[:1].upper() + token[1:] for token in tokens)


def _title_with_domain(record: AttendeeRecord) -> str:
    if not record.emails:
        return record.name
    if "@" not in record.emails[0]:
        return record.name
    domain = record.emails[0].split("@", 1)[1]
    return f"{record.name} ({domain})"


def _normalize_attendee(raw_value: str, date_value: str) -> AttendeeRecord | None:
    raw = raw_value.strip().strip('"').strip("'")
    raw = _strip_wikilink(raw)
    if not raw:
        return None

    emails: list[str] = []
    aliases: list[str] = []
    if "@" in raw and " " not in raw:
        email = raw.lower()
        if _should_skip_email(email):
            return None
        emails.append(email)
        name = _title_from_email(email)
        aliases.extend(_slug_aliases_from_email(email))
        aliases.append(email)
    else:
        name = " ".join(part for part in raw.split())
        aliases.extend(_filter_auto_aliases([name]))

    aliases.extend(_filter_auto_aliases([name]))
    aliases = _dedupe_preserve_order(aliases)
    return AttendeeRecord(raw_value=raw, name=name, emails=emails, aliases=aliases, last_touch=date_value)


def _strip_wikilink(value: str) -> str:
    match = re.fullmatch(r"\[\[([^|\]]+)\|([^\]]+)\]\]", value)
    if match:
        return match.group(2).strip()
    match = re.fullmatch(r"\[\[([^\]]+)\]\]", value)
    if match:
        return match.group(1).strip()
    return value


def _should_skip_email(email: str) -> bool:
    local, _, domain = email.partition("@")
    local = local.casefold()
    domain = domain.casefold()
    if domain == "resource.calendar.google.com":
        return True
    if local in {"all", "prague"}:
        return True
    if local.startswith("mr-"):
        return True
    if "meetingroom" in local:
        return True
    if local.startswith("office.") or local.startswith("office_"):
        return True
    return False


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if not value or key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _normalize_name_key(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9 ]+", " ", value.casefold())
    tokens = [token for token in text.split() if token]
    return " ".join(tokens)


def _normalized_name_variants(name: str) -> list[str]:
    normalized = _normalize_name_key(name)
    if not normalized:
        return []
    tokens = normalized.split()
    variants = [normalized]
    if len(tokens) == 2:
        variants.append(f"{tokens[1]} {tokens[0]}")
    return _dedupe_preserve_order(variants)


def _load_person_notes() -> list[PersonNote]:
    notes: list[PersonNote] = []
    for path in _iter_markdown_files(PEOPLE_DIR):
        if path == PEOPLE_INDEX_PATH or "Templates" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        metadata_block, body = _split_leading_metadata(text)
        metadata = _parse_metadata_block(metadata_block)
        if str(metadata.get("type", "")).strip() != "person":
            continue
        title = _find_title(body, path.stem)
        notes.append(PersonNote(path=path, title=title, metadata=metadata, body=body))
    return notes


def _build_lookup(notes: list[PersonNote]) -> tuple[dict[str, list[PersonNote]], dict[str, list[PersonNote]]]:
    by_email: dict[str, list[PersonNote]] = {}
    by_alias: dict[str, list[PersonNote]] = {}
    for note in notes:
        emails = _ensure_list(note.metadata.get("emails"))
        aliases = _ensure_list(note.metadata.get("aliases"))
        aliases.append(note.title)
        for email in emails:
            by_email.setdefault(email.casefold(), []).append(note)
        for alias in aliases:
            by_alias.setdefault(alias.casefold(), []).append(note)
            for variant in _normalized_name_variants(alias):
                by_alias.setdefault(variant, []).append(note)
    return by_email, by_alias


def _pick_note(record: AttendeeRecord, by_email: dict[str, list[PersonNote]], by_alias: dict[str, list[PersonNote]]) -> PersonNote | None:
    for email in record.emails:
        matches = by_email.get(email.casefold(), [])
        if len(matches) == 1:
            return matches[0]
    for alias in [record.name, *record.aliases]:
        matches = by_alias.get(alias.casefold(), [])
        if len(matches) == 1:
            return matches[0]
        for variant in _normalized_name_variants(alias):
            variant_matches = by_alias.get(variant, [])
            if len(variant_matches) == 1:
                return variant_matches[0]
    return None


def _max_date(a: str, b: str) -> str:
    if not a:
        return b
    if not b:
        return a
    return a if a >= b else b


def _render_person_frontmatter(metadata: dict[str, object]) -> str:
    aliases = _ensure_list(metadata.get("aliases"))
    emails = _ensure_list(metadata.get("emails"))
    lines = [
        "---",
        'type: person',
        "aliases:",
    ]
    if aliases:
        lines.extend(f"  - {_yaml_quote(alias)}" for alias in aliases)
    else:
        lines.append('  - ""')
    lines.append("emails:")
    if emails:
        lines.extend(f"  - {_yaml_quote(email)}" for email in emails)
    else:
        lines.append('  - ""')
    for key in ("org", "role", "team", "timezone", "last_touch"):
        value = str(metadata.get(key, ""))
        lines.append(f'{key}: {_yaml_quote(value)}')
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def _render_new_person_note(template_text: str, record: AttendeeRecord) -> str:
    primary_email = record.emails[0] if record.emails else ""
    query_token = primary_email or record.name
    rendered = template_text
    rendered = rendered.replace("aliases: []", "aliases:\n" + "\n".join(f"  - {_yaml_quote(alias)}" for alias in record.aliases))
    if record.emails:
        rendered = rendered.replace("emails: []", "emails:\n" + "\n".join(f"  - {_yaml_quote(email)}" for email in record.emails))
    else:
        rendered = rendered.replace("emails: []", 'emails:\n  - ""')
    rendered = rendered.replace('last_touch: YYYY-MM-DD', f'last_touch: {_yaml_quote(record.last_touch)}')
    rendered = rendered.replace("# {{title}}", f"# {record.name}")
    rendered = rendered.replace("- Last touch: YYYY-MM-DD", f"- Last touch: {record.last_touch}")
    rendered = rendered.replace("- Email:", f"- Email: {primary_email}")
    rendered = re.sub(r'(?m)^""\s*$', _yaml_quote(query_token), rendered, count=1)
    return rendered


def _update_existing_note(note: PersonNote, record: AttendeeRecord) -> str:
    metadata = dict(note.metadata)
    aliases = _dedupe_preserve_order(_ensure_list(metadata.get("aliases")) + _filter_auto_aliases([record.name]) + record.aliases)
    emails = _dedupe_preserve_order(_ensure_list(metadata.get("emails")) + record.emails)
    metadata["aliases"] = aliases
    metadata["emails"] = emails
    metadata["type"] = "person"
    metadata["org"] = str(metadata.get("org", ""))
    metadata["role"] = str(metadata.get("role", ""))
    metadata["team"] = str(metadata.get("team", ""))
    metadata["timezone"] = str(metadata.get("timezone", ""))
    if str(metadata.get("org", "")) in emails:
        metadata["org"] = ""
    else:
        metadata["org"] = str(metadata.get("org", ""))
    metadata["last_touch"] = _max_date(str(metadata.get("last_touch", "")), record.last_touch)
    body = note.body.lstrip("\ufeff")
    body = _refresh_body(body, title=note.title, emails=emails, last_touch=str(metadata["last_touch"]))
    return _render_person_frontmatter(metadata) + body


def _query_terms_block(emails: list[str]) -> str:
    if not emails:
        return '""'
    return "\n".join(_yaml_quote(email) for email in emails)


def _refresh_body(body: str, *, title: str, emails: list[str], last_touch: str) -> str:
    if not body.strip():
        return body
    body = re.sub(r"(?m)^#\s+.+$", f"# {title}", body, count=1)
    body = re.sub(r"(?m)^- Last touch:.*$", f"- Last touch: {last_touch}", body, count=1)
    primary_email = emails[0] if emails else ""
    query_terms = _query_terms_block(emails)
    if primary_email:
        body = re.sub(r"(?m)^- Email:.*$", f"- Email: {primary_email}", body, count=1)
    body = re.sub(r'(?ms)(^## Meetings\s+```query\s+path:20_Meetings\s+).+?(\s+```)', rf'\1{query_terms}\2', body, count=1)
    body = re.sub(r'(?ms)(^## Emails\s+```query\s+path:00_Mailbox\s+).+?(\s+```)', rf'\1{query_terms}\2', body, count=1)
    body = _ensure_email_section(body, query_terms)
    return body


def _ensure_email_section(body: str, query_terms: str) -> str:
    block = "\n".join(
        [
            "## Emails",
            "```query",
            "path:00_Mailbox",
            query_terms,
            "```",
            "",
        ]
    )
    if re.search(r"(?m)^## Emails\s*$", body):
        return body

    if re.search(r"(?m)^## Notes\s*$", body):
        return re.sub(r"(?m)^## Notes\s*$", block + "## Notes", body, count=1)

    return body.rstrip() + "\n\n" + block


def _merge_record(records_by_key: dict[str, AttendeeRecord], record: AttendeeRecord) -> None:
    key = record.emails[0].casefold() if record.emails else _normalize_name_key(record.name)
    if not key:
        return
    existing = records_by_key.get(key)
    if existing is None:
        records_by_key[key] = record
        return
    existing.aliases = _dedupe_preserve_order(existing.aliases + record.aliases)
    existing.emails = _dedupe_preserve_order(existing.emails + record.emails)
    existing.last_touch = _max_date(existing.last_touch, record.last_touch)


def refresh_people_layout(*, dry_run: bool) -> int:
    updated = 0
    unchanged = 0
    for note in _load_person_notes():
        before = note.path.read_text(encoding="utf-8")
        emails = _ensure_list(note.metadata.get("emails"))
        last_touch = str(note.metadata.get("last_touch", ""))
        refreshed_body = _refresh_body(note.body.lstrip("\ufeff"), title=note.title, emails=emails, last_touch=last_touch)
        after = _render_person_frontmatter(note.metadata) + refreshed_body
        if after == before:
            unchanged += 1
            continue
        if not dry_run:
            note.path.write_text(after, encoding="utf-8")
        updated += 1

    print(f"People notes refreshed: {updated}")
    print(f"People notes unchanged: {unchanged}")
    return 0


def _update_people_index(attendee_titles: list[str], dry_run: bool) -> bool:
    if not PEOPLE_INDEX_PATH.exists():
        return False
    before = PEOPLE_INDEX_PATH.read_text(encoding="utf-8")
    section_lines = ["## Contacts from meetings + emails (auto)"]
    if attendee_titles:
        section_lines.extend(f"- [[{title}]]" for title in attendee_titles)
    else:
        section_lines.append("- None")
    section = "\n".join(section_lines) + "\n\n"

    pattern = re.compile(r"(?ms)^## (?:Meeting attendees|Contacts from meetings \+ emails) \(auto\)\n.*?(?=^## |\Z)")
    if pattern.search(before):
        after = pattern.sub(section, before, count=1)
    else:
        marker = "## All known people (from notes)\n"
        if marker in before:
            after = before.replace(marker, section + marker, 1)
        else:
            after = before.rstrip() + "\n\n" + section

    if after == before:
        return False
    if not dry_run:
        PEOPLE_INDEX_PATH.write_text(after, encoding="utf-8")
    return True


def sync_people_from_meetings(*, dry_run: bool) -> int:
    if not PERSON_TEMPLATE_PATH.exists():
        raise RuntimeError(f"Missing template: {PERSON_TEMPLATE_PATH}")

    template_text = PERSON_TEMPLATE_PATH.read_text(encoding="utf-8")
    person_notes = _load_person_notes()
    by_email, by_alias = _build_lookup(person_notes)

    attendees_by_key: dict[str, AttendeeRecord] = {}
    for meeting_path in _iter_markdown_files(MEETINGS_DIR):
        text = meeting_path.read_text(encoding="utf-8")
        metadata_block, _ = _split_leading_metadata(text)
        metadata = _parse_metadata_block(metadata_block)
        attendee_values = _ensure_list(metadata.get("attendees"))
        date_value = str(metadata.get("date", ""))
        for raw_value in attendee_values:
            record = _normalize_attendee(raw_value, date_value)
            if record is None:
                continue
            _merge_record(attendees_by_key, record)

    for mailbox_path in _iter_markdown_files(MAILBOX_DIR):
        if mailbox_path.name in {"_Mailbox.md", "emails_summary.md"}:
            continue
        text = mailbox_path.read_text(encoding="utf-8")
        metadata_block, _ = _split_leading_metadata(text)
        metadata = _parse_metadata_block(metadata_block)
        date_value = str(metadata.get("last_message_at", ""))[:10]
        participant_values = _ensure_list(metadata.get("participants"))
        for raw_value in participant_values:
            record = _normalize_attendee(raw_value, date_value)
            if record is None:
                continue
            _merge_record(attendees_by_key, record)

    created = 0
    updated = 0
    unchanged = 0
    attendee_titles: list[str] = []

    for record in sorted(attendees_by_key.values(), key=lambda item: (item.name.casefold(), item.raw_value.casefold())):
        note = _pick_note(record, by_email, by_alias)
        if note is None:
            title = record.name
            filename = _sanitize_filename(title) + ".md"
            path = PEOPLE_DIR / filename
            while path.exists():
                title = _title_with_domain(record)
                path = PEOPLE_DIR / f"{_sanitize_filename(title)}.md"
                if not path.exists():
                    break
                path = PEOPLE_DIR / f"{_sanitize_filename(title + ' ' + record.emails[0])}.md"
                break
            record_for_write = AttendeeRecord(
                raw_value=record.raw_value,
                name=title,
                emails=record.emails,
                aliases=_dedupe_preserve_order(record.aliases + (_filter_auto_aliases([record.name]) if title != record.name else [])),
                last_touch=record.last_touch,
            )
            rendered = _render_new_person_note(template_text, record_for_write)
            if not dry_run:
                path.write_text(rendered, encoding="utf-8")
            created += 1
            note = PersonNote(path=path, title=record_for_write.name, metadata={"type": "person", "aliases": record_for_write.aliases, "emails": record_for_write.emails}, body=_split_leading_metadata(rendered)[1])
            person_notes.append(note)
            by_email, by_alias = _build_lookup(person_notes)
        else:
            before = note.path.read_text(encoding="utf-8") if note.path.exists() else ""
            after = _update_existing_note(note, record)
            if after != before:
                if not dry_run:
                    note.path.write_text(after, encoding="utf-8")
                updated += 1
                note.metadata = _parse_metadata_block(_split_leading_metadata(after)[0])
                note.body = _split_leading_metadata(after)[1]
            else:
                unchanged += 1
        attendee_titles.append(_find_title(note.body, note.path.stem) if note.body else note.path.stem)

    attendee_titles = sorted(set(attendee_titles), key=str.casefold)
    index_updated = _update_people_index(attendee_titles, dry_run=dry_run)

    print(f"Contacts found from meetings + mailbox thread participants: {len(attendees_by_key)}")
    print(f"Created people notes: {created}")
    print(f"Updated people notes: {updated}")
    print(f"Unchanged people notes: {unchanged}")
    print(f"People index updated: {1 if index_updated else 0}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="attendee_people_sync")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sync = sub.add_parser("sync", help="Create/update people notes from meeting attendees")
    p_sync.add_argument("--dry-run", action="store_true", help="Show what would change without writing files")

    p_refresh = sub.add_parser("refresh-layout", help="Ensure all person notes contain the expected meetings and emails sections")
    p_refresh.add_argument("--dry-run", action="store_true", help="Show what would change without writing files")

    args = parser.parse_args()
    if args.cmd == "sync":
        return sync_people_from_meetings(dry_run=bool(args.dry_run))
    if args.cmd == "refresh-layout":
        return refresh_people_layout(dry_run=bool(args.dry_run))
    parser.error(f"Unknown command: {args.cmd}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
