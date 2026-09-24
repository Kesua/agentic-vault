from __future__ import annotations

import html
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "90_System" / "Skills" / "slack_assistant"))

from wizard import handlers, state, validators  # noqa: E402
import slack_assistant as slack  # noqa: E402


class SlackUserTokenContractTests(unittest.TestCase):
    def test_manifest_requests_user_read_scopes_only(self) -> None:
        manifest = (ROOT / "90_System/Integrations/slack/app_manifest.readonly.yaml").read_text(encoding="utf-8")
        self.assertIn("    user:\n", manifest)
        self.assertIn("      - files:read", manifest)
        self.assertNotIn("    bot:\n", manifest)
        self.assertNotIn("chat:write", manifest)
        wizard_html = (ROOT / "src/wizard/web/index.html").read_text(encoding="utf-8")
        embedded = re.search(r'<pre[^>]*id="slack-manifest-code"[^>]*>(.*?)</pre>', wizard_html, re.S)
        self.assertIsNotNone(embedded)
        self.assertEqual(manifest.strip(), html.unescape(embedded.group(1)).strip())

    def test_wizard_screen_describes_user_token_and_exclusions(self) -> None:
        html = (ROOT / "src/wizard/web/index.html").read_text(encoding="utf-8")
        self.assertIn("User OAuth Token", html)
        self.assertIn("exclude", html.lower())
        self.assertNotIn("Bot User OAuth Token", html)

    def test_wizard_accepts_user_token_and_rejects_bot_token(self) -> None:
        self.assertTrue(validators.format_check_slack("xoxp-test-user")["valid"])
        self.assertTrue(validators.format_check_slack("xoxe.xoxp-test-user")["valid"])
        self.assertFalse(validators.format_check_slack("xoxb-test-bot")["valid"])

    def test_wizard_saves_user_token_in_user_token_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            wizard_state = state.WizardState()
            with (
                mock.patch.object(handlers, "SECRETS_DIR", Path(tmp)),
                mock.patch.object(handlers.validators, "live_check_slack", return_value={"valid": True, "team_id": "T123", "user_id": "U123"}),
                mock.patch.object(handlers.state, "load", return_value=wizard_state),
                mock.patch.object(handlers.state, "save"),
            ):
                result = handlers.handle_slack_save({"token": "xoxp-test-user", "alias": "private"}, {})
            self.assertTrue(result["valid"])
            self.assertEqual("xoxp-test-user", (Path(tmp) / "slack_user_token_private.txt").read_text(encoding="utf-8"))
            self.assertFalse((Path(tmp) / "slack_token_private.txt").exists())

    def test_runtime_loads_user_token_and_exclusion_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "workspaces.json"
            config_path.write_text(json.dumps({"workspaces": [{
                "alias": "private",
                "team_id": "T123",
                "user_token_file": "90_System/secrets/slack_user_token_private.txt",
                "self_user_ids": ["U123"],
                "exclude_conversation_ids": ["C999"],
                "download": {"enabled": False},
            }]}), encoding="utf-8")
            with mock.patch.object(slack, "CONFIG_PATH", config_path):
                workspace = slack.load_workspace_configs()["private"]
        self.assertEqual("user", workspace.user_auth.source)
        self.assertEqual(("U123",), workspace.self_user_ids)
        self.assertEqual(("C999",), workspace.exclude_conversation_ids)

    def test_discovery_uses_user_visibility_and_exclusions(self) -> None:
        workspace = slack.WorkspaceConfig(
            alias="private", team_id="T123", bot_auth=None,
            user_auth=slack.SlackAuthConfig("user", Path("unused-token-file")),
            self_user_ids=("U123",), exclude_conversation_ids=("C2",),
            download_policy=slack.WorkspaceDownloadPolicy(False, 1024, (".txt",)),
        )
        visible = [
            slack.SlackConversation("C1", "general", "public_channel", False),
            slack.SlackConversation("C2", "excluded", "public_channel", False),
            slack.SlackConversation("D1", "", "im", True, "U456"),
        ]
        client = mock.Mock()
        client.users.return_value = {"U456": {"name": "Colleague"}}
        client.conversations.side_effect = lambda types: [item for item in visible if item.kind in types]
        with mock.patch.object(slack, "get_client", return_value=client):
            channels = slack.workspace_conversations(workspace)
            all_types = slack.workspace_conversations(workspace, include_dm=True, include_mpim=True)
        self.assertEqual(["C1"], [item.id for item in channels])
        self.assertEqual(["C1", "D1"], [item.id for item in all_types])
        self.assertTrue(all(item.auth_source == "user" for item in all_types))

    def test_wizard_rejects_legacy_bot_allowlist_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(handlers, "INTEGRATIONS_DIR", Path(tmp)):
                result = handlers.handle_slack_save_config({"config": {"workspaces": [{
                    "alias": "private", "token_file": "90_System/secrets/slack_token_private.txt",
                    "allow_conversations": [{"id": "C123"}],
                }]}}, {})
            self.assertFalse(result["saved"])
            self.assertFalse((Path(tmp) / "slack" / "workspaces.json").exists())

    def test_old_bot_token_does_not_mark_user_token_setup_connected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secrets_dir = Path(tmp) / "secrets"
            secrets_dir.mkdir()
            (secrets_dir / "slack_token_private.txt").write_text("old-bot-token", encoding="utf-8")
            state_file = Path(tmp) / "wizard_state.json"
            state_file.write_text('{"slack_connected": true, "slack_workspaces": ["private"]}', encoding="utf-8")
            with (
                mock.patch.object(state, "SECRETS_DIR", secrets_dir),
                mock.patch.object(state, "STATE_FILE", state_file),
            ):
                loaded = state.load()
            self.assertFalse(loaded.slack_connected)
            self.assertEqual([], loaded.slack_workspaces)

    def test_initial_load_includes_user_visible_direct_messages(self) -> None:
        wizard_state = state.WizardState(slack_connected=True)
        with (
            mock.patch.object(handlers.state, "load", return_value=wizard_state),
            mock.patch.object(handlers, "_run_initial_load_command", return_value={"ok": True}) as runner,
        ):
            result = handlers.handle_initial_load_run({"services": ["messages"], "days_back": 2}, {})
        self.assertTrue(result["ok"])
        command = runner.call_args.args[0]
        self.assertIn("--include-dm", command)
        self.assertIn("--include-mpim", command)


if __name__ == "__main__":
    unittest.main()
