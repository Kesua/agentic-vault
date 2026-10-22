from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("vault_commit.py")
SPEC = importlib.util.spec_from_file_location("vault_commit", MODULE_PATH)
assert SPEC and SPEC.loader
vault_commit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = vault_commit
SPEC.loader.exec_module(vault_commit)


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True
    ).stdout.strip()


class VaultCommitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        root = Path(self._temp.name)
        self.remote = root / "remote.git"
        self.repo = root / "vault"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.remote)], check=True, capture_output=True)
        subprocess.run(["git", "clone", str(self.remote), str(self.repo)], check=True, capture_output=True)
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        git(self.repo, "checkout", "-b", "main")
        (self.repo / "README.md").write_text("vault\n", encoding="utf-8")
        git(self.repo, "add", "README.md")
        git(self.repo, "commit", "-m", "init")
        git(self.repo, "push", "-u", "origin", "main")

    def tearDown(self) -> None:
        self._temp.cleanup()

    def run_main(self, *args: str) -> tuple[int, str]:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = vault_commit.main(["--repo", str(self.repo), "--routine", "day-start", "--date", "2026-10-22", *args])
        return code, stdout.getvalue()

    def test_commits_only_routine_paths(self) -> None:
        (self.repo / "10_DailyBriefs").mkdir()
        (self.repo / "10_DailyBriefs" / "brief.md").write_text("# Tasks\n", encoding="utf-8")
        (self.repo / "notes.md").write_text("private draft\n", encoding="utf-8")
        git(self.repo, "add", "notes.md")

        code, output = self.run_main()

        self.assertEqual(0, code)
        self.assertIn("routine: day-start 2026-10-22", output)
        self.assertEqual("routine: day-start 2026-10-22", git(self.repo, "log", "-1", "--format=%s"))
        self.assertEqual("10_DailyBriefs/brief.md", git(self.repo, "show", "--name-only", "--format=", "HEAD"))
        self.assertIn("A  notes.md", git(self.repo, "status", "--porcelain"))

    def test_nothing_to_commit(self) -> None:
        code, output = self.run_main()
        self.assertEqual(0, code)
        self.assertIn("Nothing to commit", output)

    def test_push_refused_without_allow_listed_url(self) -> None:
        code, output = self.run_main("--push")
        self.assertEqual(vault_commit.EXIT_PUSH_REFUSED, code)
        self.assertIn(vault_commit.ALLOWED_PUSH_URL_KEY, output)

    def test_push_refused_for_different_url(self) -> None:
        git(self.repo, "config", vault_commit.ALLOWED_PUSH_URL_KEY, "https://github.com/someone/else.git")
        code, output = self.run_main("--push")
        self.assertEqual(vault_commit.EXIT_PUSH_REFUSED, code)
        self.assertIn("does not match", output)

    def test_push_to_allow_listed_remote(self) -> None:
        git(self.repo, "config", vault_commit.ALLOWED_PUSH_URL_KEY, str(self.remote))
        (self.repo / "40_People").mkdir()
        (self.repo / "40_People" / "Person.md").write_text("# Person\n", encoding="utf-8")

        code, output = self.run_main("--push")

        self.assertEqual(0, code, output)
        self.assertEqual(git(self.repo, "rev-parse", "HEAD"), git(self.remote, "rev-parse", "main"))

    def test_rejected_push_is_reported_without_merging(self) -> None:
        git(self.repo, "config", vault_commit.ALLOWED_PUSH_URL_KEY, str(self.remote))
        other = Path(self._temp.name) / "other"
        subprocess.run(["git", "clone", str(self.remote), str(other)], check=True, capture_output=True)
        git(other, "config", "user.email", "test@example.com")
        git(other, "config", "user.name", "Test")
        (other / "remote.md").write_text("remote\n", encoding="utf-8")
        git(other, "add", "remote.md")
        git(other, "commit", "-m", "remote change")
        git(other, "push", "origin", "main")
        (self.repo / "20_Meetings").mkdir()
        (self.repo / "20_Meetings" / "meeting.md").write_text("# Meeting\n", encoding="utf-8")

        code, output = self.run_main("--push")

        self.assertEqual(vault_commit.EXIT_PUSH_REJECTED, code)
        self.assertIn("ahead 1 and behind 1", output)
        self.assertFalse((self.repo / "remote.md").exists())
        self.assertEqual("routine: day-start 2026-10-22", git(self.repo, "log", "-1", "--format=%s"))


if __name__ == "__main__":
    unittest.main()
