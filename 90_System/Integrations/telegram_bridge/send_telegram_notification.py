from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from telegram_bridge import (
    REPO_ROOT,
    BridgeConfig,
    BridgeError,
    _append_log,
    _ensure_dirs,
    load_config,
    send_message,
)


DEFAULT_CONFIG_PATH = REPO_ROOT / "90_System" / "secrets" / "telegram_bridge.env"
MAX_NOTIFICATION_CHARS = 4000


class NotificationValidationError(ValueError):
    """Raised when a notification cannot be sent safely."""


def _encoding_error_fields(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, UnicodeEncodeError):
        return {}
    offending = exc.object[exc.start : exc.end]
    return {
        "error_encoding": exc.encoding,
        "error_reason": exc.reason,
        "error_codepoints": [f"U+{ord(char):04X}" for char in offending],
    }


def select_notification_chat_id(config: BridgeConfig) -> int:
    chat_count = len(config.allowed_chat_ids)
    if chat_count != 1:
        raise NotificationValidationError(
            "TELEGRAM_ALLOWED_CHAT_IDS must contain exactly one chat id "
            f"for notifications; found {chat_count}."
        )
    return next(iter(config.allowed_chat_ids))


def validate_html_message(html: str) -> str:
    if not html.strip():
        raise NotificationValidationError("Notification HTML must not be empty.")
    if len(html) > MAX_NOTIFICATION_CHARS:
        raise NotificationValidationError(
            f"Notification HTML exceeds the {MAX_NOTIFICATION_CHARS}-character limit."
        )
    return html


def send_html_notification(
    config: BridgeConfig,
    html: str,
    *,
    dry_run: bool = False,
) -> Any:
    validated_html = validate_html_message(html)
    chat_id = select_notification_chat_id(config)
    _ensure_dirs(config)

    if dry_run:
        _append_log(
            config,
            "info",
            "Telegram notification dry run validated",
            char_count=len(validated_html),
        )
        return None

    try:
        result = send_message(config, chat_id, validated_html, parse_mode="HTML")
    except Exception as exc:
        _append_log(
            config,
            "error",
            "Telegram notification failed",
            char_count=len(validated_html),
            error_type=type(exc).__name__,
            **_encoding_error_fields(exc),
        )
        raise

    message_id = result.get("message_id") if isinstance(result, dict) else None
    _append_log(
        config,
        "info",
        "Telegram notification sent",
        char_count=len(validated_html),
        message_id=message_id,
    )
    return result


def _safe_error_text(exc: Exception, config: BridgeConfig | None = None) -> str:
    if isinstance(exc, FileNotFoundError):
        return str(exc)
    if isinstance(exc, NotificationValidationError):
        return str(exc)
    if config is None and isinstance(exc, ValueError) and not isinstance(exc, BridgeError):
        return "Telegram bridge configuration is invalid."

    text = str(exc)
    if config is not None and config.bot_token:
        text = text.replace(config.bot_token, "[redacted]")
    return text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Send one HTML notification through the existing Telegram bridge bot."
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the existing telegram_bridge.env file",
    )
    parser.add_argument("--html", required=True, help="Telegram-compatible HTML message")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate configuration and message without calling Telegram",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config: BridgeConfig | None = None

    try:
        config = load_config(Path(args.config).resolve())
    except (BridgeError, FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {_safe_error_text(exc)}", file=sys.stderr)
        return 2

    try:
        send_html_notification(config, args.html, dry_run=args.dry_run)
    except NotificationValidationError as exc:
        print(f"Validation error: {_safe_error_text(exc, config)}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Telegram notification failed: {_safe_error_text(exc, config)}", file=sys.stderr)
        return 1

    action = "validated" if args.dry_run else "sent"
    print(f"Telegram notification {action} ({len(args.html)} characters).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
