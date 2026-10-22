import importlib.util
import sys
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILLS = HERE.parent


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


mm = _load("meeting_metadata", HERE / "meeting_metadata.py")

RULES = [
    mm.ProjectRule("Acme - Analytics", ("acme.example",), ("Acme", "Analytics Phase 2"), ("acme-analytics",)),
    mm.ProjectRule("Globex - Data", ("globex.example",), ("Globex", "GBX")),
    mm.ProjectRule("Initech", ("initech.example",), ("Initech",)),
    mm.ProjectRule("Internal - HR Agent", (), ("HRBOT", "HR Agent")),
    mm.ProjectRule("Research Paper", (), ("Research Paper",)),
    mm.ProjectRule("Umbrella Steel", ("umbrella.example",), ("Umbrella",)),
    mm.ProjectRule("Kavarna", ("kavarna.example",), ("Kavarna",)),
]

LEGACY_NOTE = """---
type: meeting_note
date: 2026-10-07
start: 13:30
end: 14:30
meeting_title: "Weekly update: [[30_Projects/Analytics/Analytics|Analytics]] Phase 2"
project: ""
attendees:
  - "[[Alex Client|alex.client@acme.example]]"
  - "owner@company.example"
  - "sam.client@acme.example"
## Calendar (auto)
- Account: private
- Meet: https://meet.example.com/abc

## Preparation
- ...

## Fireflies Transcript (auto)

[00:00:28] [[Owner Person|Owner Pérson]]: Good morning.
[00:00:40] Žofie Nováková: Hi: how is it going?
[00:01:05] [[Owner Person|Owner Pérson]]: Fine.
[??:??:??] Unknown: ...
[00:02:00] [[Alex Client|Alex]] Client: Hello.

- Synced: 2026-10-07T15:00:00+02:00
"""


class InferProjectTests(unittest.TestCase):
    def test_client_domain_wins_for_recurring_title_without_client_name(self):
        match = mm.infer_project(RULES, title="Weekly update- Analytics Phase 3", attendees=["kim@acme.example", "owner@company.example"])
        self.assertEqual(match.project, "Acme - Analytics")

    def test_title_keyword_disambiguates_multiple_client_domains(self):
        match = mm.infer_project(RULES, title="QA review Initech", attendees=["a@globex.example", "b@initech.example"])
        self.assertEqual(match.project, "Initech")
        match = mm.infer_project(RULES, title="[[30_Projects/Analytics/Analytics|Analytics]] Globex - data",
                                 attendees=["a@globex.example", "b@acme.example"])
        self.assertEqual(match.project, "Globex - Data")

    def test_internal_title_keyword_diacritics_and_subdomain(self):
        self.assertEqual(mm.infer_project(RULES, title="Project \"HR Agent\": Steering").project, "Internal - HR Agent")
        self.assertEqual(mm.infer_project(RULES, title="Kavárna/Team - Research Paper review",
                                         attendees=["x@mail.kavarna.example"]).project, "Kavarna")

    def test_conflicts_and_missing_signals_stay_empty(self):
        conflict = mm.infer_project(RULES, title="Follow up Research Paper/Team", attendees=["x@umbrella.example"])
        self.assertEqual((conflict.project, conflict.reason), ("", "ambiguous"))
        self.assertEqual(conflict.candidates, ("Research Paper", "Umbrella Steel"))
        two_domains = mm.infer_project(RULES, title="Sync", attendees=["a@globex.example", "b@acme.example"])
        self.assertEqual((two_domains.project, two_domains.reason), ("", "ambiguous"))
        self.assertEqual(mm.infer_project(RULES, title="Owner / Colleague 1on1", attendees=["c@company.example"]).reason, "none")
        self.assertEqual(mm.infer_project(RULES, title="Initechno review").project, "")  # whole words only

    def test_slack_channel_signal(self):
        self.assertEqual(mm.infer_project(RULES, slack_channel="#acme-analytics").project, "Acme - Analytics")


class ProjectMapFileTests(unittest.TestCase):
    def test_shipped_example_map_loads_and_avoids_shared_domains(self):
        rules = mm.load_project_map()
        self.assertTrue(all(r.name and not r.name.startswith("_") for r in rules))
        domains = {d for r in rules for d in r.domains}
        self.assertFalse(domains & {"gmail.com", "outlook.com", "icloud.com"})

    def test_missing_or_empty_map_means_no_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(mm.load_project_map(root / "missing.json"), [])
            empty = root / "empty.json"
            empty.write_text("", encoding="utf-8")
            self.assertEqual(mm.load_project_map(empty), [])
            no_projects = root / "no_projects.json"
            no_projects.write_text('{"_about": ["x"], "projects": {}}', encoding="utf-8")
            self.assertEqual(mm.load_project_map(no_projects), [])
        result = mm.apply_metadata(LEGACY_NOTE, [], speakers=["Kim"])
        self.assertEqual((result.project_status, result.speakers), ("none", ["Kim"]))

    def test_example_entry_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "map.json"
            path.write_text('{"projects": {"Example Client - Pilot": {"domains": ["@Example.com"], '
                            '"title_keywords": ["Example Client"], "slack_channels": ["#Example-Client-Pilot"]}}}',
                            encoding="utf-8")
            rules = mm.load_project_map(path)
        self.assertEqual(rules, [mm.ProjectRule("Example Client - Pilot", ("example.com",), ("Example Client",),
                                                ("example-client-pilot",))])
        self.assertEqual(mm.infer_project(rules, title="Weekly", attendees=["a@example.com"]).project, "Example Client - Pilot")


class FrontmatterTests(unittest.TestCase):
    def test_speakers_from_transcript_strip_links_dedupe_and_skip_unknown(self):
        self.assertEqual(mm.speakers_from_note(LEGACY_NOTE), ["Owner Pérson", "Žofie Nováková", "Alex Client"])
        self.assertEqual(mm.speakers_from_note("---\ntype: x\n---\nno transcript"), [])

    def test_legacy_unclosed_note_gets_project_speakers_and_closing_delimiter_only(self):
        result = mm.apply_metadata(LEGACY_NOTE, RULES, speakers=mm.speakers_from_note(LEGACY_NOTE))
        self.assertTrue(result.changed and result.repaired_frontmatter)
        self.assertEqual(result.project_status, "set")
        fm = mm.split_frontmatter(result.text)
        self.assertTrue(fm.closed)
        self.assertEqual(mm.get_value(fm, "project"), "Acme - Analytics")
        self.assertEqual(mm.get_value(fm, "speakers"), ["Owner Pérson", "Žofie Nováková", "Alex Client"])
        self.assertEqual(mm.get_value(fm, "attendees"), mm.get_value(mm.split_frontmatter(LEGACY_NOTE), "attendees"))
        self.assertIn('---\n## Calendar (auto)\n', result.text)
        self.assertTrue(result.text.endswith(LEGACY_NOTE.split("  - \"sam.client@acme.example\"\n", 1)[1]))
        again = mm.apply_metadata(result.text, RULES, speakers=mm.speakers_from_note(result.text))
        self.assertFalse(again.changed)

    def test_manual_project_is_never_overwritten(self):
        text = LEGACY_NOTE.replace('project: ""', 'project: "[[30_Projects/Journal/Research Paper|Research Paper]]"')
        result = mm.apply_metadata(text, RULES)
        self.assertEqual(result.project_status, "kept")
        self.assertIn('project: "[[30_Projects/Journal/Research Paper|Research Paper]]"', result.text)

    def test_inline_comment_and_flow_list_values(self):
        fm = mm.split_frontmatter('---\nproject: ""  # note\nspeakers: []\nsource: calendar # x\n---\n')
        self.assertEqual(mm.get_value(fm, "project"), "")
        self.assertEqual(mm.get_value(fm, "speakers"), [])
        self.assertEqual(mm.get_value(fm, "source"), "calendar")

    def test_note_without_frontmatter_is_untouched(self):
        text = "# Notes\ntype: meeting_note\nproject: \"\"\n"
        result = mm.apply_metadata(text, RULES, speakers=["A"])
        self.assertFalse(result.has_frontmatter or result.changed)

    def test_legacy_note_missing_opening_delimiter_is_repaired(self):
        text = '\r\ntype: meeting_note\r\nmeeting_title: "Initech"\r\nproject: ""\r\nattendees:\r\n  - "a@x.example"\r\n## Calendar (auto)\r\n- UID: 1\r\n'
        result = mm.apply_metadata(text, [mm.ProjectRule("Initech", (), ("Initech",))])
        self.assertTrue(result.repaired_frontmatter)
        self.assertEqual(result.text, '---\r\ntype: meeting_note\r\nmeeting_title: "Initech"\r\nproject: "Initech"\r\n'
                                      'attendees:\r\n  - "a@x.example"\r\n---\r\n## Calendar (auto)\r\n- UID: 1\r\n')


class BackfillTests(unittest.TestCase):
    def test_backfill_dry_run_then_write_is_idempotent_and_date_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inside = root / "2026" / "10" / "07" / "1330 - Weekly update- Analytics Phase 2.md"
            outside = root / "2026" / "10" / "20" / "1330 - Weekly update- Analytics Phase 2.md"
            ambiguous = root / "2026" / "10" / "08" / "1000 - Research Paper.md"
            for path, text in ((inside, LEGACY_NOTE), (outside, LEGACY_NOTE),
                               (ambiguous, '---\nmeeting_title: "Research Paper demo"\nproject: ""\nattendees:\n  - "x@umbrella.example"\n---\nbody\n')):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8", newline="")

            dry = mm.backfill(root, date(2026, 10, 1), date(2026, 10, 15), RULES, dry_run=True)
            self.assertEqual(inside.read_text(encoding="utf-8"), LEGACY_NOTE)
            self.assertEqual(dry["stats"]["scanned"], 2)
            self.assertEqual(dry["stats"]["project_set"], 1)
            self.assertEqual(dry["stats"]["speakers_set"], 1)
            self.assertEqual(dry["ambiguous"], [("2026/10/08/1000 - Research Paper.md", ("Research Paper", "Umbrella Steel"))])

            crlf = root / "2026" / "10" / "09" / "1400 - Weekly update- Analytics Phase 2.md"
            crlf.parent.mkdir(parents=True, exist_ok=True)
            crlf.write_bytes(LEGACY_NOTE.replace("\n", "\r\n").encode("utf-8"))

            mm.backfill(root, date(2026, 10, 1), date(2026, 10, 15), RULES, dry_run=False)
            self.assertIn('project: "Acme - Analytics"', inside.read_text(encoding="utf-8"))
            crlf_bytes = crlf.read_bytes()
            self.assertNotIn(b"\n", crlf_bytes.replace(b"\r\n", b""))
            body = LEGACY_NOTE.split("## Calendar (auto)\n", 1)[1].replace("\n", "\r\n").encode("utf-8")
            self.assertTrue(crlf_bytes.endswith(body))
            self.assertEqual(outside.read_text(encoding="utf-8"), LEGACY_NOTE)
            second = mm.backfill(root, date(2026, 10, 1), date(2026, 10, 15), RULES, dry_run=False)
            self.assertEqual(second["stats"]["changed"], 0)


class SyncIntegrationTests(unittest.TestCase):
    def test_gcal_render_closes_frontmatter_infers_project_and_keeps_manual_values(self):
        gcal = _load("gcal_today", SKILLS / "gcal_today" / "gcal_today.py")
        template = (gcal.MEETING_TEMPLATE_PATH).read_text(encoding="utf-8")
        tz = datetime.now().astimezone().tzinfo
        ev = gcal.CalendarEvent(
            key="uid__2026-10-07", fireflies_cal_id=None, account="private", calendar_id="primary", event_id="e1",
            title="Weekly update: Analytics Phase 2", start_local=datetime(2026, 10, 7, 13, 30, tzinfo=tz),
            end_local=datetime(2026, 10, 7, 14, 30, tzinfo=tz), html_link=None, meet_link="https://meet.example.com/abc",
            location=None, description=None, attendees=["owner@company.example", "sam.client@acme.example"],
        )
        fresh = gcal._render_meeting_note(template, ev, project_rules=RULES)
        fm = mm.split_frontmatter(fresh)
        self.assertTrue(fm.closed)
        self.assertEqual(mm.get_value(fm, "project"), "Acme - Analytics")
        self.assertEqual(mm.get_value(fm, "attendees"), ["owner@company.example", "sam.client@acme.example"])
        self.assertEqual(mm.get_value(fm, "source"), "google_calendar")
        self.assertEqual(mm.get_value(fm, "speakers"), [])
        self.assertIn("## Calendar (auto)", fm.body)

        existing = mm.apply_metadata(LEGACY_NOTE.replace('project: ""', 'project: "Research Paper"'), RULES,
                                     speakers=["Žofie Nováková"]).text
        tail = gcal._extract_preserved_tail(existing)
        rerendered = gcal._render_meeting_note(template, ev, preserved_tail=tail, existing_text=existing, project_rules=RULES)
        fm2 = mm.split_frontmatter(rerendered)
        self.assertEqual(mm.get_value(fm2, "project"), "Research Paper")
        self.assertEqual(mm.get_value(fm2, "speakers"), ["Žofie Nováková"])
        self.assertIn("## Fireflies Transcript (auto)", rerendered)

        no_map = gcal._render_meeting_note(template, ev, project_rules=[])
        self.assertEqual(mm.get_value(mm.split_frontmatter(no_map), "project"), "")

    def test_fireflies_sets_speakers_from_sentences_and_keeps_attendees(self):
        ff = _load("fireflies_sync", SKILLS / "fireflies_sync" / "fireflies_sync.py")
        sentences = [ff.FirefliesSentence(1, "Žofie Nováková", "a", 1.0), ff.FirefliesSentence(2, None, "b", 2.0),
                     ff.FirefliesSentence(3, "žofie nováková", "c", 3.0), ff.FirefliesSentence(4, "Owner Pérson", "d", 4.0)]
        out = ff._apply_note_metadata(LEGACY_NOTE, RULES, sentences)
        fm = mm.split_frontmatter(out)
        self.assertEqual(mm.get_value(fm, "speakers"), ["Žofie Nováková", "Owner Pérson"])
        self.assertEqual(mm.get_value(fm, "project"), "Acme - Analytics")
        self.assertEqual(len(mm.get_value(fm, "attendees")), 3)
        self.assertEqual(ff._apply_note_metadata(out, RULES, []), out)


if __name__ == "__main__":
    unittest.main()
