from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("sync_claude_code.py")


AGENTS = """# Agent Instructions

## Session bootstrap
- This `AGENTS.md` is loaded automatically. At session start, read `SOUL.md` and the short core `MEMORY.md`.
- Read a topic memory file in `90_System/Memory/` only when the task touches that topic.

## Canonical paths for locally stored data
- Workblocks live under `80_Workblocks/`.

## Empty section

## Skill routing
- Claude Code mirrors in `.claude/skills/` use hyphens instead of underscores.
- `adhoc_example`: Example skill.
  - nested detail

## Workblock protocol
- End with exactly one `Workblock:` receipt.
"""

SOUL = """# SOUL

## Identity
- Pragmatic partner.

## Behavioral Defaults
- Prefer simple solutions.
"""

MEMORY = """# MEMORY

## Durable Rules
- THIS PRIVATE MEMORY RULE MUST NOT BE COPIED.
"""


class ClaudeMdGenerationTests(unittest.TestCase):
    def test_claude_md_is_complete_and_uses_claude_skill_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = root / "90_System" / "Skills" / "claude_code_mirror" / "sync_claude_code.py"
            script.parent.mkdir(parents=True)
            shutil.copy2(SCRIPT, script)
            (root / "AGENTS.md").write_text(AGENTS, encoding="utf-8")
            (root / "SOUL.md").write_text(SOUL, encoding="utf-8")
            (root / "MEMORY.md").write_text(MEMORY, encoding="utf-8")
            skill = root / ".agents/skills/adhoc_example/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text('---\nname: "adhoc_example"\ndescription: "Example skill"\n---\n\n# Example\n', encoding="utf-8")

            result = subprocess.run(
                [sys.executable, str(script)], cwd=root, text=True, capture_output=True, check=False
            )

            self.assertEqual(0, result.returncode, result.stderr)
            generated = (root / "CLAUDE.md").read_text(encoding="utf-8")
            self.assertIn("- `adhoc-example`: Example skill.", generated)
            self.assertIn("  - nested detail", generated)
            self.assertIn("Prefer simple solutions.", generated)
            self.assertIn("End with exactly one `Workblock:` receipt.", generated)
            self.assertIn("read only the short core `MEMORY.md`", generated)
            self.assertIn("Read a topic memory file", generated)
            self.assertNotIn("## Empty section", generated)
            self.assertNotIn("use hyphens instead of underscores", generated)
            self.assertNotIn("THIS PRIVATE MEMORY RULE", generated)
            self.assertNotIn("## Working memory", generated)
            self.assertTrue((root / ".claude/skills/adhoc-example/SKILL.md").exists())


if __name__ == "__main__":
    unittest.main()
