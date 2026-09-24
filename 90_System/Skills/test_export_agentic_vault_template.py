from __future__ import annotations

import subprocess
import tempfile
import unittest
import re
import shutil
from pathlib import Path


SCRIPT = Path(__file__).with_name("export_agentic_vault_template.ps1")


class AgenticVaultExportTests(unittest.TestCase):
    def test_default_export_preserves_curated_google_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "agentic-vault"
            google_runtime = destination / "90_System/Skills/google_drive_assistant/google_drive_assistant.py"
            google_runtime.parent.mkdir(parents=True)
            google_runtime.write_text("curated Google editing runtime\n", encoding="utf-8")

            result = subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(SCRIPT), "-Destination", str(destination)],
                text=True, capture_output=True, check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("curated Google editing runtime\n", google_runtime.read_text(encoding="utf-8"))

    def test_preserve_existing_keeps_distribution_files_and_adds_new_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "agentic-vault"
            destination.mkdir()
            readme = destination / "README.md"
            readme.write_text("Curated setup wizard guide\n", encoding="utf-8")

            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SCRIPT),
                    "-Destination",
                    str(destination),
                    "-PreserveExisting",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual("Curated setup wizard guide\n", readme.read_text(encoding="utf-8"))
            self.assertTrue((destination / "90_System/Skills/workblocks/workblocks.py").exists())

    def test_export_omits_credentials_from_direct_and_recursive_copies(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source"
            destination = Path(tmp) / "distribution"
            fixture_script = source / "90_System" / "Skills" / SCRIPT.name
            fixture_script.parent.mkdir(parents=True)
            shutil.copy2(SCRIPT, fixture_script)
            (source / ".claude/hooks").mkdir(parents=True)

            for relative in re.findall(
                r'Copy-FileRelative -RelativeSource "([^"]+)"',
                SCRIPT.read_text(encoding="utf-8-sig"),
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture content\n", encoding="utf-8")

            for relative in (
                "AgentPrompts.md",
                "requirements.txt",
                "60_SOPs/StartHere.md",
                "60_SOPs/_HowIWork.md",
                "60_SOPs/_AgentGuide.md",
                "00_Mailbox/_Mailbox.md",
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture content\n", encoding="utf-8")

            for relative in (
                ".agents/skills/demo/SKILL.md",
                "90_System/Skills/demo/run.py",
                "90_System/Integrations/Documentation/guide.md",
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("safe fixture\n", encoding="utf-8")

            for relative in (
                "90_System/Integrations/slack/app_info.txt",
                ".agents/skills/demo/.env.local",
                ".claude/skills/demo/credential.txt",
            ):
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture-secret\n", encoding="utf-8")

            hidden_credential = source / "90_System/Integrations/Documentation/notes.md"
            hidden_credential.write_text(
                "xoxb-" + "123456789012-abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8"
            )
            generated_doc = source / "60_SOPs/_AgentGuide.md"
            generated_doc.write_text(
                "xoxb-" + "123456789012-abcdefghijklmnopqrstuvwxyz\n", encoding="utf-8"
            )

            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(fixture_script),
                    "-Destination",
                    str(destination),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertTrue((destination / ".agents/skills/demo/SKILL.md").exists())
            self.assertTrue((destination / "90_System/Skills/demo/run.py").exists())
            self.assertTrue((destination / "90_System/Integrations/Documentation/guide.md").exists())
            self.assertFalse((destination / "90_System/Integrations/slack/app_info.txt").exists())
            self.assertFalse((destination / ".agents/skills/demo/.env.local").exists())
            self.assertFalse((destination / ".claude/skills/demo/credential.txt").exists())
            self.assertFalse((destination / "90_System/Integrations/Documentation/notes.md").exists())
            self.assertFalse((destination / "60_SOPs/_AgentGuide.md").exists())

    def test_export_contains_only_workblock_skeleton_and_helper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            destination = Path(tmp) / "agentic-vault"
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(SCRIPT),
                    "-Destination",
                    str(destination),
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, result.returncode, result.stderr)
            exported_workblocks = sorted(
                path.name for path in (destination / "80_Workblocks").glob("*.md")
            )
            self.assertEqual(["README.md", "_Template.md"], exported_workblocks)
            self.assertTrue(
                (destination / "90_System" / "Skills" / "workblocks" / "workblocks.py").exists()
            )
            for relative in (
                ".agents/skills/adhoc_client_meeting_summary/SKILL.md",
                ".agents/skills/adhoc_dph_invoicing/SKILL.md",
                ".agents/skills/adhoc_smartscout_db/SKILL.md",
                ".agents/skills/investment_analyst/SKILL.md",
                ".claude/skills/investment-analyst/SKILL.md",
                "90_System/Skills/dph_invoicing/dph_invoicing.py",
                "90_System/Skills/smartscout_db/adhoc_smartscout_db.py",
                "90_System/Skills/investment_funnel/DESIGN.md",
                "90_System/Skills/meeting_attendees_people_sync/people_enrich.py",
                "90_System/Skills/claude_code_mirror/sync_claude_code.py",
                "90_System/Skills/claude_code_mirror/test_sync_claude_code.py",
            ):
                self.assertFalse((destination / relative).exists(), relative)
            people_skill = (
                destination / "90_System/Skills/meeting_attendees_people_sync/SKILL.md"
            ).read_text(encoding="utf-8-sig")
            self.assertNotIn("people_enrich.py", people_skill)
            how_i_work = (destination / "60_SOPs/_HowIWork.md").read_text(
                encoding="utf-8-sig"
            )
            self.assertNotIn("FLO", how_i_work)
            requirements = (destination / "requirements.txt").read_text(encoding="utf-8-sig")
            self.assertNotIn("pyodbc", requirements)
            self.assertNotIn("jan.papousek", SCRIPT.read_text(encoding="utf-8-sig"))
            agents = (destination / "AGENTS.md").read_text(encoding="utf-8-sig")
            claude = (destination / "CLAUDE.md").read_text(encoding="utf-8-sig")
            for document in (agents, claude):
                self.assertIn("Workblock protocol", document)
                self.assertIn("Workblock: not needed", document)


if __name__ == "__main__":
    unittest.main()
