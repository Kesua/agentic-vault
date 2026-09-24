from __future__ import annotations

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

import send_telegram_notification as notifier
import telegram_bridge as bridge


def make_config(*, chat_ids: set[int] | None = None, token: str = "test-token") -> bridge.BridgeConfig:
    return bridge.BridgeConfig(
        bot_token=token,
        allowed_user_ids={123},
        allowed_chat_ids={456} if chat_ids is None else chat_ids,
        codex_command="codex",
        vault_root=Path.cwd(),
        log_dir=Path.cwd() / "logs",
        runtime_dir=Path.cwd() / "runtime",
        timeout_seconds=10,
        poll_timeout_seconds=5,
        accept_plain_text=True,
    )


class TelegramBridgeSendMessageTests(unittest.TestCase):
    def test_plain_message_keeps_existing_payload(self) -> None:
        config = make_config()
        with mock.patch.object(bridge, "_telegram_request", return_value={"message_id": 1}) as request_mock:
            result = bridge.send_message(config, 456, "plain")

        self.assertEqual({"message_id": 1}, result)
        self.assertEqual(
            {"chat_id": "456", "text": "plain"},
            request_mock.call_args.args[2],
        )

    def test_html_message_sets_parse_mode(self) -> None:
        config = make_config()
        with mock.patch.object(bridge, "_telegram_request", return_value={"message_id": 2}) as request_mock:
            bridge.send_message(config, 456, "<b>done</b>", parse_mode="HTML")

        self.assertEqual(
            {"chat_id": "456", "text": "<b>done</b>", "parse_mode": "HTML"},
            request_mock.call_args.args[2],
        )


class NotificationHelperTests(unittest.TestCase):
    def test_existing_environment_variable_names_load_without_new_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "telegram_bridge.env"
            config_path.write_text(
                "\n".join(
                    [
                        "TELEGRAM_BOT_TOKEN=test-token",
                        "TELEGRAM_ALLOWED_USER_IDS=123",
                        "TELEGRAM_ALLOWED_CHAT_IDS=456",
                    ]
                ),
                encoding="utf-8",
            )
            with mock.patch.dict("os.environ", {}, clear=True):
                config = bridge.load_config(config_path)

        self.assertEqual("test-token", config.bot_token)
        self.assertEqual({123}, config.allowed_user_ids)
        self.assertEqual({456}, config.allowed_chat_ids)

    def test_exactly_one_allowed_chat_is_selected(self) -> None:
        self.assertEqual(456, notifier.select_notification_chat_id(make_config()))

    def test_no_allowed_chat_is_rejected(self) -> None:
        with self.assertRaisesRegex(notifier.NotificationValidationError, "found 0"):
            notifier.select_notification_chat_id(make_config(chat_ids=set()))

    def test_multiple_allowed_chats_are_rejected(self) -> None:
        with self.assertRaisesRegex(notifier.NotificationValidationError, "found 2"):
            notifier.select_notification_chat_id(make_config(chat_ids={456, 789}))

    def test_empty_html_is_rejected(self) -> None:
        with self.assertRaisesRegex(notifier.NotificationValidationError, "must not be empty"):
            notifier.validate_html_message("  \n")

    def test_oversized_html_is_rejected(self) -> None:
        with self.assertRaisesRegex(notifier.NotificationValidationError, "exceeds"):
            notifier.validate_html_message("x" * (notifier.MAX_NOTIFICATION_CHARS + 1))

    def test_dry_run_does_not_call_telegram(self) -> None:
        config = make_config()
        with (
            mock.patch.object(notifier, "send_message") as send_mock,
            mock.patch.object(notifier, "_ensure_dirs"),
            mock.patch.object(notifier, "_append_log") as log_mock,
        ):
            result = notifier.send_html_notification(config, "<b>test</b>", dry_run=True)

        self.assertIsNone(result)
        send_mock.assert_not_called()
        log_mock.assert_called_once()
        self.assertNotIn("<b>test</b>", str(log_mock.call_args))

    def test_html_notification_uses_html_parse_mode(self) -> None:
        config = make_config()
        with (
            mock.patch.object(notifier, "send_message", return_value={"message_id": 5}) as send_mock,
            mock.patch.object(notifier, "_ensure_dirs"),
            mock.patch.object(notifier, "_append_log"),
        ):
            result = notifier.send_html_notification(config, "<b>test</b>")

        self.assertEqual({"message_id": 5}, result)
        send_mock.assert_called_once_with(config, 456, "<b>test</b>", parse_mode="HTML")

    def test_api_failure_returns_nonzero_without_exposing_token(self) -> None:
        config = make_config(token="super-secret-token")
        stderr = io.StringIO()
        with (
            mock.patch.object(notifier, "load_config", return_value=config),
            mock.patch.object(
                notifier,
                "send_html_notification",
                side_effect=bridge.BridgeError("request failed for super-secret-token"),
            ),
            redirect_stderr(stderr),
        ):
            exit_code = notifier.main(["--html", "<b>test</b>"])

        self.assertEqual(1, exit_code)
        self.assertNotIn("super-secret-token", stderr.getvalue())
        self.assertIn("[redacted]", stderr.getvalue())

    def test_runtime_encoding_error_is_not_misreported_as_invalid_configuration(self) -> None:
        config = make_config()
        error = UnicodeEncodeError("ascii", "kůň", 1, 2, "ordinal not in range")

        text = notifier._safe_error_text(error, config)

        self.assertIn("ascii", text)
        self.assertNotIn("configuration is invalid", text)

    def test_configuration_value_error_remains_safely_generic(self) -> None:
        text = notifier._safe_error_text(ValueError("bad secret value"))

        self.assertEqual("Telegram bridge configuration is invalid.", text)

    def test_encoding_error_log_fields_do_not_include_message_text(self) -> None:
        error = UnicodeEncodeError("ascii", "kůň", 1, 2, "ordinal not in range")

        fields = notifier._encoding_error_fields(error)

        self.assertEqual("ascii", fields["error_encoding"])
        self.assertEqual(["U+016F"], fields["error_codepoints"])
        self.assertNotIn("kůň", str(fields))

    def test_cli_dry_run_succeeds_without_telegram_call(self) -> None:
        config = make_config()
        stdout = io.StringIO()
        with (
            mock.patch.object(notifier, "load_config", return_value=config),
            mock.patch.object(notifier, "send_html_notification") as send_mock,
            redirect_stdout(stdout),
        ):
            exit_code = notifier.main(["--html", "<b>test</b>", "--dry-run"])

        self.assertEqual(0, exit_code)
        send_mock.assert_called_once_with(config, "<b>test</b>", dry_run=True)
        self.assertIn("validated", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
