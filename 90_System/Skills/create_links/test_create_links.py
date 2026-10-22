from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("create_links.py")
SPEC = importlib.util.spec_from_file_location("create_links", MODULE_PATH)
assert SPEC and SPEC.loader
create_links = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = create_links
SPEC.loader.exec_module(create_links)


def _person(stem: str, aliases: list[str]) -> str:
    alias_lines = "\n".join(f'  - "{alias}"' for alias in aliases)
    return f"---\ntype: person\naliases:\n{alias_lines}\n---\n\n# {stem}\n"


class CreateLinksRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._temp.name)
        self.people = self.tmp / "40_People"
        self.people.mkdir()
        self._orig_root = create_links.REPO_ROOT
        self._orig_sources = create_links.ENTITY_SOURCE_DIRS
        create_links.REPO_ROOT = self.tmp
        create_links.ENTITY_SOURCE_DIRS = {"person": self.people}

    def tearDown(self) -> None:
        create_links.REPO_ROOT = self._orig_root
        create_links.ENTITY_SOURCE_DIRS = self._orig_sources
        self._temp.cleanup()

    def _write(self, stem: str, aliases: list[str]) -> None:
        (self.people / f"{stem}.md").write_text(_person(stem, aliases), encoding="utf-8")

    def _rewrite(self, text: str) -> str:
        registry, ambiguous = create_links._build_alias_registry()
        matcher = create_links.AliasMatcher(registry, blocked=set(ambiguous))
        return create_links._rewrite_body(text, matcher)[0]

    def test_full_name_links_to_own_note_not_other_first_name_alias(self) -> None:
        self._write("Alex Novak", ["Alex Novak", "Alex"])
        self._write("Alex Smith", ["Alex Smith"])
        result = self._rewrite("Call with Alex Smith and Alex Novak.")
        self.assertIn("[[Alex Smith|Alex Smith]]", result)
        self.assertIn("[[Alex Novak|Alex Novak]]", result)
        self.assertNotIn("[[Alex Novak|Alex]]", result)

    def test_note_title_is_candidate_even_without_alias(self) -> None:
        self._write("Alex Novak", ["Alex Novak", "Alex"])
        self._write("Alex Smith", [])
        self.assertEqual(self._rewrite("Alex Smith joined."), "[[Alex Smith|Alex Smith]] joined.")

    def test_shared_first_name_alias_is_ambiguous(self) -> None:
        self._write("Alex Novak", ["Alex Novak", "Alex"])
        self._write("Alex Smith", ["Alex Smith"])
        registry, ambiguous = create_links._build_alias_registry()
        self.assertNotIn("Alex", registry)
        self.assertIn("Alex", ambiguous)
        self.assertEqual(self._rewrite("Ask Alex about it."), "Ask Alex about it.")

    def test_unique_first_name_alias_still_links(self) -> None:
        self._write("Alex Novak", ["Alex Novak", "Alex"])
        self._write("Sam Rivera", ["Sam Rivera"])
        self.assertEqual(self._rewrite("Ask Alex about it."), "Ask [[Alex Novak|Alex]] about it.")

    def test_single_token_alias_not_linked_before_capitalized_word(self) -> None:
        self._write("Alex Novak", ["Alex Novak", "Alex"])
        self.assertEqual(self._rewrite("Alex Dvořák said hi"), "Alex Dvořák said hi")
        self.assertEqual(self._rewrite("Alex Šťastný said hi"), "Alex Šťastný said hi")
        self.assertEqual(self._rewrite("Alex said hi"), "[[Alex Novak|Alex]] said hi")
        self.assertEqual(self._rewrite("Alex\nNext line"), "[[Alex Novak|Alex]]\nNext line")

    def test_duplicate_note_does_not_steal_full_name(self) -> None:
        self._write("Alex Smith", ["Alex Smith"])
        self._write("Alex Smith Alex Smith", ["Alex Smith"])
        self.assertEqual(self._rewrite("Alex Smith"), "[[Alex Smith|Alex Smith]]")

    def test_ambiguous_full_name_blocks_shorter_alias(self) -> None:
        self._write("Alex Novak", ["Alex Novak", "Alex"])
        self._write("Alex Smith (example.com)", ["Alex Smith"])
        self._write("Alex Smith (example.org)", ["Alex Smith"])
        self.assertEqual(self._rewrite("Alex Smith"), "Alex Smith")

    def test_duplicate_note_does_not_make_first_name_ambiguous(self) -> None:
        self._write("Eva Moreau", ["Eva Moreau", "Eva"])
        self._write("Eva Moreau Eva Moreau", ["Eva Moreau"])
        self.assertEqual(self._rewrite("Thanks, Eva"), "Thanks, [[Eva Moreau|Eva]]")

    def test_alias_inside_email_or_dotted_token_not_linked(self) -> None:
        self._write("Sam Rivera", ["Sam Rivera", "Sam"])
        text = "Mail Sam.Taylor@example.com and Dr.Sam shop. Bye Sam."
        self.assertEqual(
            self._rewrite(text),
            "Mail Sam.Taylor@example.com and Dr.Sam shop. Bye [[Sam Rivera|Sam]].",
        )

    def test_existing_wikilinks_untouched(self) -> None:
        self._write("Alex Smith", ["Alex Smith"])
        text = "See [[Alex Smith|Alex Smith]] and `Alex Smith`."
        self.assertEqual(self._rewrite(text), text)


class NameTokenTests(unittest.TestCase):
    def test_is_name_token(self) -> None:
        self.assertTrue(create_links._is_name_token("Alex"))
        self.assertTrue(create_links._is_name_token("Lukáš"))
        self.assertTrue(create_links._is_name_token("O'Neill"))
        self.assertFalse(create_links._is_name_token("alex.novak"))
        self.assertFalse(create_links._is_name_token("a@example.com"))
        self.assertFalse(create_links._is_name_token("Alex Smith"))


if __name__ == "__main__":
    unittest.main()
