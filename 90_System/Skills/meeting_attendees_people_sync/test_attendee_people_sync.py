from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("attendee_people_sync.py")
SPEC = importlib.util.spec_from_file_location("attendee_people_sync", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

TEMPLATE = MODULE_PATH.parents[3] / "40_People" / "Templates" / "person_TEMPLATE.md"


def _person(
    stem: str, *, aliases: list[str], emails: list[str] | None = None, last_touch: str = ""
) -> str:
    alias_lines = "\n".join(f'  - "{alias}"' for alias in aliases) or '  - ""'
    email_lines = "\n".join(f'  - "{email}"' for email in (emails or [])) or '  - ""'
    return (
        f"---\ntype: person\naliases:\n{alias_lines}\nemails:\n{email_lines}\n"
        f'org: ""\nrole: ""\nteam: ""\ntimezone: ""\nlast_touch: "{last_touch}"\n---\n\n'
        f"# {stem}\n\n## Quick facts\n- Last touch: {last_touch}\n\n## Notes\n- Open loops:\n"
    )


def _meeting(day: str, attendees: list[str]) -> str:
    lines = "\n".join(f'  - "{attendee}"' for attendee in attendees)
    return f"---\ndate: {day}\nattendees:\n{lines}\n---\n\n# Meeting\n"


def _metadata(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    return MODULE._parse_metadata_block(MODULE._split_leading_metadata(text)[0])


class AttendeePeopleSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._temp.name)
        self.people = self.tmp / "40_People"
        (self.people / "Templates").mkdir(parents=True)
        shutil.copy(TEMPLATE, self.people / "Templates" / "person_TEMPLATE.md")
        (self.tmp / "20_Meetings").mkdir()
        (self.tmp / "00_Mailbox").mkdir()
        names = (
            "REPO_ROOT",
            "MEETINGS_DIR",
            "MAILBOX_DIR",
            "PEOPLE_DIR",
            "PEOPLE_INDEX_PATH",
            "PERSON_TEMPLATE_PATH",
        )
        self._saved = {name: getattr(MODULE, name) for name in names}
        MODULE.REPO_ROOT = self.tmp
        MODULE.MEETINGS_DIR = self.tmp / "20_Meetings"
        MODULE.MAILBOX_DIR = self.tmp / "00_Mailbox"
        MODULE.PEOPLE_DIR = self.people
        MODULE.PEOPLE_INDEX_PATH = self.people / "_PeopleIndex.md"
        MODULE.PERSON_TEMPLATE_PATH = self.people / "Templates" / "person_TEMPLATE.md"

    def tearDown(self) -> None:
        for name, value in self._saved.items():
            setattr(MODULE, name, value)
        self._temp.cleanup()

    def _write_person(self, stem: str, **kwargs: object) -> Path:
        path = self.people / f"{stem}.md"
        path.write_text(_person(stem, **kwargs), encoding="utf-8")
        return path

    def _meeting_file(self, name: str, day: str, attendees: list[str]) -> None:
        (self.tmp / "20_Meetings" / name).write_text(_meeting(day, attendees), encoding="utf-8")

    def _sync(self, run_date: str = "2026-10-22") -> None:
        MODULE.sync_people_from_meetings(dry_run=False, run_date=run_date)

    def _people_files(self) -> list[str]:
        return sorted(path.stem for path in self.people.glob("*.md") if path.stem != "_PeopleIndex")

    def test_name_only_attendee_matches_existing_note_without_duplicate(self) -> None:
        path = self._write_person("Alex Novak", aliases=["Alex Novak"], last_touch="2026-06-08")
        self._meeting_file("m1.md", "2026-10-20", ["Alex Novak"])
        self._sync()
        self._sync()
        self.assertEqual(self._people_files(), ["Alex Novak"])
        self.assertEqual(_metadata(path)["last_touch"], "2026-10-20")

    def test_existing_file_without_alias_is_reused_not_duplicated(self) -> None:
        # Even when lookup fails (no aliases, different H1), "X Y.md" is reused, never "X Y X Y.md".
        path = self.people / "Sam Rivera.md"
        path.write_text(_person("Sam Rivera", aliases=[]).replace("# Sam Rivera", "# Someone"), encoding="utf-8")
        self._meeting_file("m1.md", "2026-10-01", ["Sam Rivera"])
        self._sync()
        self.assertEqual(self._people_files(), ["Sam Rivera"])

    def test_taken_file_name_never_gets_raw_suffix_or_crashes(self) -> None:
        # "Sam Rivera.md" is not a person note, so lookup misses and the file name is taken.
        (self.people / "Sam Rivera.md").write_text("---\ntype: project\n---\n\n# Sam Rivera\n", encoding="utf-8")
        self._write_person("Sam Rivera (example.com)", aliases=["Sam R"])
        self._meeting_file("m1.md", "2026-10-01", ["sam.rivera@example.com", "Sam Rivera"])
        self._sync()
        self.assertEqual(self._people_files(), ["Sam Rivera", "Sam Rivera (example.com)"])
        emails = _metadata(self.people / "Sam Rivera (example.com).md")["emails"]
        self.assertIn("sam.rivera@example.com", emails)

    def test_new_attendee_note_created_once(self) -> None:
        self._meeting_file("m1.md", "2026-10-01", ["Eva Nová"])
        self._meeting_file("m2.md", "2026-10-02", ["Eva Nová"])
        self._sync()
        self._sync()
        self.assertEqual(self._people_files(), ["Eva Nová"])

    def test_last_touch_never_after_run_date(self) -> None:
        path = self._write_person(
            "Chris Taylor",
            aliases=["Chris Taylor"],
            emails=["chris.taylor@example.com"],
            last_touch="2026-11-04",
        )
        self._meeting_file("past.md", "2026-10-15", ["chris.taylor@example.com"])
        self._meeting_file("future.md", "2026-11-04", ["chris.taylor@example.com"])
        self._meeting_file("future2.md", "2026-11-04", ["new.person@example.com"])
        self._sync(run_date="2026-10-22")
        self.assertEqual(_metadata(path)["last_touch"], "2026-10-15")
        self.assertIn("- Last touch: 2026-10-15", path.read_text(encoding="utf-8"))
        self.assertEqual(_metadata(self.people / "New Person.md")["last_touch"], "")

    def test_refresh_layout_clears_future_last_touch(self) -> None:
        path = self._write_person("Alex Novak", aliases=["Alex Novak"], last_touch="2026-11-04")
        MODULE.refresh_people_layout(dry_run=False, run_date="2026-10-22")
        self.assertEqual(_metadata(path)["last_touch"], "")

    def test_people_index_links_to_file_name(self) -> None:
        index = self.people / "_PeopleIndex.md"
        index.write_text("# People\n\n## All known people (from notes)\n", encoding="utf-8")
        path = self.people / "Alex Novak.md"
        path.write_text(
            _person("Alex Novak", aliases=["Alex Novak"]).replace("# Alex Novak", "# Alex N."),
            encoding="utf-8",
        )
        self._meeting_file("m1.md", "2026-10-01", ["Alex Novak"])
        self._sync()
        text = index.read_text(encoding="utf-8")
        self.assertIn("- [[Alex Novak]]", text)
        self.assertNotIn("[[Alex N.]]", text)

    def test_lookup_counts_each_note_once(self) -> None:
        self._write_person("Alex Novak", aliases=["Alex Novak"])
        _, by_alias = MODULE._build_lookup(MODULE._load_person_notes())
        self.assertEqual(len(by_alias["alex novak"]), 1)

    def test_repeated_name_notes_are_ignored(self) -> None:
        self._write_person("Alex Novak", aliases=["Alex Novak"])
        self._write_person("Alex Novak Alex Novak", aliases=["Alex Novak"])
        record = MODULE._normalize_attendee("Alex Novak", "2026-10-01")
        by_email, by_alias = MODULE._build_lookup(MODULE._load_person_notes())
        self.assertEqual(MODULE._pick_note(record, by_email, by_alias).path.stem, "Alex Novak")
        self.assertTrue(MODULE._is_repeated_name("Alex Novak Alex Novak"))
        self.assertFalse(MODULE._is_repeated_name("Maria Lopez Garcia"))

    def test_clamp_date(self) -> None:
        self.assertEqual(MODULE._clamp_date("2026-11-04", "2026-10-22"), "")
        self.assertEqual(MODULE._clamp_date("2026-10-22T10:00:00", "2026-10-22"), "2026-10-22")
        self.assertEqual(MODULE._max_date("2026-11-04", "2026-10-01", "2026-10-22"), "2026-10-01")


if __name__ == "__main__":
    unittest.main()
