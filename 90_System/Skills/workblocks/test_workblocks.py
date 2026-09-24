from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("workblocks.py")
SPEC = importlib.util.spec_from_file_location("workblocks", MODULE_PATH)
assert SPEC and SPEC.loader
workblocks = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = workblocks
SPEC.loader.exec_module(workblocks)


VALID_WORKBLOCK = """---
type: workblock
status: active
scope: "[[30_Projects/Example/Example]]"
created: 2026-09-16
updated: 2026-09-16T20:30:00+02:00
backfilled: false
confidence: high
---

# Example — Ship feature

- Goal: Ship the feature.
- Current state: Tests are passing.
- Next action: Deploy it.
- Blocker / decision: None.
- Key files: `app.py`
- Source sessions: codex:test-session
"""


class WorkblockTests(unittest.TestCase):
    def test_parse_and_validate_accepts_complete_workblock(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Example - Ship feature.md").write_text(VALID_WORKBLOCK, encoding="utf-8")

            result = workblocks.validate_workblocks(root)

            self.assertEqual([], result["errors"])
            self.assertEqual([], result["warnings"])
            self.assertEqual(1, result["checked"])

    def test_validate_rejects_bad_enum_date_heading_and_missing_body_field(self) -> None:
        broken = VALID_WORKBLOCK.replace("status: active", "status: paused")
        broken = broken.replace("created: 2026-09-16", "created: yesterday")
        broken = broken.replace("# Example — Ship feature", "## Wrong heading")
        broken = broken.replace("- Next action: Deploy it.\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Broken.md").write_text(broken, encoding="utf-8")

            result = workblocks.validate_workblocks(root)

            messages = "\n".join(item["message"] for item in result["errors"])
            self.assertIn("status", messages)
            self.assertIn("created", messages)
            self.assertIn("level-1 heading", messages)
            self.assertIn("Next action", messages)

    def test_validate_requires_confidence_for_backfilled_workblock(self) -> None:
        content = VALID_WORKBLOCK.replace("backfilled: false", "backfilled: true")
        content = content.replace("confidence: high\n", "")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Backfilled.md").write_text(content, encoding="utf-8")

            result = workblocks.validate_workblocks(root)

            self.assertTrue(any("confidence" in item["message"] for item in result["errors"]))

    def test_validate_warns_but_does_not_fail_for_long_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / (("A" * 121) + ".md")).write_text(VALID_WORKBLOCK, encoding="utf-8")

            result = workblocks.validate_workblocks(root)

            self.assertEqual([], result["errors"])
            self.assertTrue(any("120" in item["message"] for item in result["warnings"]))

    def test_list_filters_status_and_ranks_query_relevance(self) -> None:
        completed = VALID_WORKBLOCK.replace("status: active", "status: completed")
        unrelated = VALID_WORKBLOCK.replace("# Example — Ship feature", "# General — Grocery list")
        unrelated = unrelated.replace("Ship the feature.", "Buy groceries.")
        unrelated = unrelated.replace("Deploy it.", "Visit the shop.")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Example - Ship feature.md").write_text(VALID_WORKBLOCK, encoding="utf-8")
            (root / "Example - Completed.md").write_text(completed, encoding="utf-8")
            (root / "General - Grocery list.md").write_text(unrelated, encoding="utf-8")

            found = workblocks.find_workblocks(root, {"active", "blocked"}, "ship feature")

            self.assertEqual(["Example - Ship feature.md"], [item["path"].name for item in found])

    def test_safe_filename_replaces_windows_characters_truncates_and_resolves_collision(self) -> None:
        existing = {"Project - Intent.md"}

        collision = workblocks.safe_filename("Project", "Intent", "abcdef12", existing)
        long_name = workblocks.safe_filename("P" * 90, "I" * 90, "feedface", set())
        unsafe = workblocks.safe_filename('AUX: Client?', 'Fix <thing> / now*', "12345678", set())

        self.assertEqual("Project - Intent - abcdef12.md", collision)
        self.assertLessEqual(len(long_name), 120)
        self.assertNotRegex(unsafe, r'[<>:"/\\|?*]')

    def test_atomic_write_replaces_content_without_leaving_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("old", encoding="utf-8")

            workblocks.atomic_write_text(path, "new")

            self.assertEqual("new", path.read_text(encoding="utf-8"))
            self.assertEqual(["state.json"], [item.name for item in Path(tmp).iterdir()])

    def test_redaction_removes_common_secrets_and_authorization_headers(self) -> None:
        source = (
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.secret.signature\n"
            "api_key=sk-test_abcdefghijklmnopqrstuvwxyz123456\n"
            "password: super-secret-value\n"
            "safe text"
        )

        redacted = workblocks.redact_secrets(source)

        self.assertNotIn("eyJhbGci", redacted)
        self.assertNotIn("sk-test", redacted)
        self.assertNotIn("super-secret-value", redacted)
        self.assertIn("safe text", redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED]"), 3)


class HistoryTests(unittest.TestCase):
    def test_default_claude_project_folder_uses_claude_path_encoding(self) -> None:
        encoded = workblocks._default_claude_root(
            Path(r"C:\Users\example\Vault")
        )

        self.assertEqual("C--Users-example-Vault", encoded.name)

    def _codex_session(
        self,
        path: Path,
        session_id: str,
        cwd: Path,
        *,
        source: object = "vscode",
        thread_source: object = "user",
        originator: str = "codex_vscode",
        prompt: str = "Continue the migration",
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = [
            {
                "timestamp": "2026-09-15T10:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": session_id,
                    "session_id": session_id,
                    "cwd": str(cwd),
                    "source": source,
                    "thread_source": thread_source,
                    "originator": originator,
                },
            },
            {
                "timestamp": "2026-09-15T10:00:01Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": prompt}],
                },
            },
        ]
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    def test_index_history_includes_roots_and_excludes_noninteractive_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            vault.mkdir()
            codex = root / "codex"
            claude = root / "claude-project"
            output = root / "out"
            index = root / "session_index.jsonl"

            self._codex_session(codex / "included.jsonl", "codex-root", vault)
            self._codex_session(
                codex / "automation.jsonl", "codex-auto", vault, thread_source="automation"
            )
            self._codex_session(
                codex / "subagent.jsonl",
                "codex-sub",
                vault,
                source={"subagent": {"kind": "spawned"}},
                thread_source="subagent",
            )
            self._codex_session(
                codex / "guardian.jsonl", "codex-guardian", vault, thread_source="guardian_review"
            )
            self._codex_session(
                codex / "exec.jsonl", "codex-exec", vault, source="exec", originator="codex_exec"
            )
            self._codex_session(codex / "other.jsonl", "codex-other", root / "other-vault")
            index.write_text(
                json.dumps(
                    {
                        "id": "codex-root",
                        "thread_name": "Migration api_key=sk-test_abcdefghijklmnopqrstuvwxyz123456",
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            claude.mkdir()
            (claude / "root.jsonl").write_text(
                json.dumps(
                    {
                        "type": "user",
                        "sessionId": "claude-root",
                        "cwd": str(vault),
                        "timestamp": "2026-09-14T09:00:00Z",
                        "message": {"role": "user", "content": "Finish the project"},
                        "isSidechain": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (claude / "stale-cwd.jsonl").write_text(
                json.dumps(
                    {
                        "type": "user",
                        "sessionId": "claude-stale-cwd",
                        "cwd": str(root / "historical-checkout"),
                        "timestamp": "2026-09-13T09:00:00Z",
                        "message": {"role": "user", "content": "Resume vault work"},
                        "isSidechain": False,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (claude / "sidechain.jsonl").write_text(
                json.dumps(
                    {
                        "type": "user",
                        "sessionId": "claude-side",
                        "cwd": str(vault),
                        "timestamp": "2026-09-14T09:00:00Z",
                        "message": {"role": "user", "content": "subtask"},
                        "isSidechain": True,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            nested = claude / "subagents"
            nested.mkdir()
            (nested / "ignored.jsonl").write_text("{}\n", encoding="utf-8")

            manifest = workblocks.index_history(
                vault,
                output,
                claude_root=claude,
                codex_root=codex,
                codex_index=index,
            )

            eligible = {(item["provider"], item["session_id"]) for item in manifest["eligible"]}
            self.assertEqual(
                {
                    ("codex", "codex-root"),
                    ("claude", "claude-root"),
                    ("claude", "claude-stale-cwd"),
                },
                eligible,
            )
            title = next(item["title"] for item in manifest["eligible"] if item["provider"] == "codex")
            self.assertEqual("Migration api_key=[REDACTED]", title)
            self.assertNotIn("sk-test", json.dumps(manifest))
            reasons = {item["reason"] for item in manifest["excluded"]}
            self.assertTrue({"automation", "subagent", "guardian_review", "codex_exec", "cwd"} <= reasons)

    def test_index_history_preserves_resume_mappings_and_does_not_duplicate_sessions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            vault.mkdir()
            codex = root / "codex"
            output = root / "out"
            self._codex_session(codex / "one.jsonl", "session-one", vault)

            first = workblocks.index_history(vault, output, codex_root=codex, claude_root=root / "none")
            state_path = output / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["sessions"]["codex:session-one"] = {
                "outcome": "skipped",
                "reason": "not_stateful",
            }
            workblocks.atomic_write_json(state_path, state)
            second = workblocks.index_history(vault, output, codex_root=codex, claude_root=root / "none")

            self.assertEqual(1, len(first["eligible"]))
            self.assertEqual(1, len(second["eligible"]))
            resumed = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual("not_stateful", resumed["sessions"]["codex:session-one"]["reason"])

    def test_extract_history_outputs_only_requested_redacted_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            vault.mkdir()
            codex = root / "codex"
            output = root / "out"
            self._codex_session(
                codex / "one.jsonl",
                "session-one",
                vault,
                prompt="Use api_key=sk-test_abcdefghijklmnopqrstuvwxyz123456 to finish",
            )
            self._codex_session(codex / "two.jsonl", "session-two", vault, prompt="Other task")
            manifest = workblocks.index_history(vault, output, codex_root=codex, claude_root=root / "none")

            extracted = workblocks.extract_history(
                output / "manifest.json", ["codex:session-one"], redact=True
            )

            self.assertEqual(["codex:session-one"], [item["key"] for item in extracted])
            serialized = json.dumps(extracted)
            self.assertNotIn("sk-test", serialized)
            self.assertIn("[REDACTED]", serialized)
            self.assertNotIn("Other task", serialized)

    def test_apply_backfill_is_idempotent_resumable_and_preserves_live_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / "backfill"
            output.mkdir()
            workblock_root = root / "80_Workblocks"
            workblock_root.mkdir()
            manifest = {
                "version": 1,
                "counts": {"scanned": 4, "eligible": 3, "excluded": 1},
                "eligible": [
                    {"key": "codex:one", "timestamp": "2026-01-01T10:00:00Z"},
                    {"key": "codex:two", "timestamp": "2026-01-02T10:00:00Z"},
                    {"key": "codex:three", "timestamp": "2026-01-03T10:00:00Z"},
                ],
            }
            manifest_path = output / "manifest.json"
            workblocks.atomic_write_json(manifest_path, manifest)
            workblocks.atomic_write_json(
                output / "state.json",
                {"version": 1, "manifest": "manifest.json", "batch_size": 20, "sessions": {}},
            )
            decisions = {
                "default": {"outcome": "skipped", "reason": "not_stateful"},
                "workblocks": [
                    {
                        "scope": "general",
                        "scope_label": "General",
                        "intent": "Long-running migration",
                        "status": "completed",
                        "confidence": "medium",
                        "goal": "Complete the migration.",
                        "current_state": "Historical implementation completed.",
                        "next_action": "None.",
                        "blocker": "None.",
                        "key_files": ["app.py"],
                        "indices": [1, 2],
                    }
                ],
            }
            decisions_path = output / "decisions.json"
            workblocks.atomic_write_json(decisions_path, decisions)

            first = workblocks.apply_backfill_decisions(
                manifest_path, decisions_path, workblock_root, batch_size=2
            )
            second = workblocks.apply_backfill_decisions(
                manifest_path, decisions_path, workblock_root, batch_size=2
            )

            self.assertEqual(2, first["mapped"])
            self.assertEqual(1, first["skipped"])
            self.assertEqual(0, first["failed"])
            self.assertEqual(1, first["created"])
            self.assertEqual(1, first["merged"])
            self.assertEqual(1, second["created"])
            self.assertEqual(0, second["created_this_run"])
            self.assertEqual(1, len(list(workblock_root.glob("*.md"))))
            state = json.loads((output / "state.json").read_text(encoding="utf-8"))
            self.assertEqual("mapped", state["sessions"]["codex:one"]["outcome"])
            self.assertEqual("not_stateful", state["sessions"]["codex:three"]["reason"])

            path = workblock_root / "General - Long-running migration.md"
            live = path.read_text(encoding="utf-8")
            live = live.replace("status: completed", "status: active")
            live = live.replace("backfilled: true", "backfilled: false")
            live = live.replace("Historical implementation completed.", "Live work is newer.")
            path.write_text(live, encoding="utf-8")
            workblocks.apply_backfill_decisions(
                manifest_path, decisions_path, workblock_root, batch_size=2
            )
            preserved = path.read_text(encoding="utf-8")
            self.assertIn("status: active", preserved)
            self.assertIn("backfilled: false", preserved)
            self.assertIn("Live work is newer.", preserved)


class WorkblockCliTests(unittest.TestCase):
    def test_list_json_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "80_Workblocks").mkdir()
            (root / "80_Workblocks" / "Example - Ship feature.md").write_text(
                VALID_WORKBLOCK, encoding="utf-8"
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--vault-root",
                    str(root),
                    "list",
                    "--statuses",
                    "active,blocked",
                    "--query",
                    "ship",
                    "--json",
                ],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual("Example - Ship feature.md", Path(payload[0]["path"]).name)


if __name__ == "__main__":
    unittest.main()
