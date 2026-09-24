"""Local onboarding checks that do not contact external services."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.wizard import state


ROOT = Path(__file__).resolve().parents[1]


class OnboardingContractTests(unittest.TestCase):
    def test_wizard_progress_uses_ignored_setup_path(self) -> None:
        self.assertEqual(state.STATE_FILE, ROOT / "_setup" / "wizard_state.json")
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("_setup/wizard_state.json", ignore)
        self.assertIn("src/wizard_state.json", ignore)

    def test_removed_credentials_clear_saved_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            progress = temp_root / "wizard_state.json"
            progress.write_text(
                json.dumps({
                    "google_credentials_uploaded": True,
                    "google_accounts": ["private"],
                    "gcal_private_authed": True,
                    "gmail_private_authed": True,
                    "gdrive_private_authed": True,
                    "todoist_connected": True,
                    "fireflies_connected": True,
                    "clockify_connected": True,
                    "telegram_connected": True,
                    "slack_connected": True,
                }),
                encoding="utf-8",
            )
            with (
                mock.patch.object(state, "STATE_FILE", progress),
                mock.patch.object(state, "LEGACY_STATE_FILE", temp_root / "legacy.json"),
                mock.patch.object(state, "SECRETS_DIR", temp_root / "secrets"),
                mock.patch.object(state, "INTEGRATIONS_DIR", temp_root / "integrations"),
            ):
                loaded = state.load()
        self.assertFalse(loaded.google_credentials_uploaded)
        self.assertEqual(loaded.google_accounts, [])
        for field in (
            "gcal_private_authed", "gmail_private_authed", "gdrive_private_authed",
            "todoist_connected", "fireflies_connected", "clockify_connected",
            "telegram_connected", "slack_connected",
        ):
            self.assertFalse(getattr(loaded, field), field)

    def test_legacy_progress_is_read_without_rewriting_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            legacy = temp_root / "legacy.json"
            legacy.write_text('{"local_ai_selected": true}', encoding="utf-8")
            current = temp_root / "setup" / "wizard_state.json"
            with (
                mock.patch.object(state, "STATE_FILE", current),
                mock.patch.object(state, "LEGACY_STATE_FILE", legacy),
                mock.patch.object(state, "SECRETS_DIR", temp_root / "secrets"),
                mock.patch.object(state, "INTEGRATIONS_DIR", temp_root / "integrations"),
            ):
                loaded = state.load()
                self.assertTrue(loaded.local_ai_selected)
                state.save(loaded)
            self.assertTrue(current.exists())
            self.assertEqual(legacy.read_text(encoding="utf-8"), '{"local_ai_selected": true}')

    def test_slack_requires_token_and_workspace_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            temp_root = Path(temp)
            secrets = temp_root / "secrets"
            secrets.mkdir()
            (secrets / "slack_user_token_private.txt").write_text("placeholder", encoding="utf-8")
            integrations = temp_root / "integrations"
            with (
                mock.patch.object(state, "SECRETS_DIR", secrets),
                mock.patch.object(state, "INTEGRATIONS_DIR", integrations),
            ):
                self.assertFalse(state._auto_detect(state.WizardState()).slack_connected)
                config = integrations / "slack" / "workspaces.json"
                config.parent.mkdir(parents=True)
                config.write_text(json.dumps({"workspaces": [{
                    "alias": "private",
                    "user_token_file": "90_System/secrets/slack_user_token_private.txt",
                }]}), encoding="utf-8")
                self.assertTrue(state._auto_detect(state.WizardState()).slack_connected)

    def test_manual_guide_uses_runtime_drive_paths(self) -> None:
        guide = (ROOT / "HOW_TO_INITIALIZE.md").read_text(encoding="utf-8")
        self.assertIn("gdrive_oauth_client_private.json", guide)
        self.assertIn("gdrive_token_private.json", guide)
        self.assertNotIn("google_drive_oauth_client", guide)

    def test_wizard_explains_recurring_sync_is_separate(self) -> None:
        html = (ROOT / "src" / "wizard" / "web" / "index.html").read_text(encoding="utf-8")
        self.assertIn("regular_day_start", html)
        self.assertIn("regular_day_end", html)
        self.assertIn("Initial load runs once", html)


if __name__ == "__main__":
    unittest.main()
