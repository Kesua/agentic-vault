"""API endpoint handlers -- all routes that the wizard frontend calls."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from . import agent_cli, google_auth_helper, state, validators

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
INTEGRATIONS_DIR = REPO_ROOT / "90_System" / "Integrations"


def register_routes(routes: dict) -> None:
    """Populate the route table used by server.py."""
    routes["GET /api/status"] = handle_status
    routes["GET /api/prerequisites"] = handle_prerequisites
    routes["GET /api/assistant/status"] = handle_assistant_status
    routes["POST /api/assistant/install"] = handle_assistant_install
    routes["POST /api/assistant/launch"] = handle_assistant_launch
    routes["POST /api/google/upload-credentials"] = handle_google_upload
    routes["POST /api/google/start-auth"] = handle_google_start_auth
    routes["GET /api/google/auth-status"] = handle_google_auth_status
    routes["POST /api/todoist/save-token"] = handle_todoist_save
    routes["POST /api/telegram/save-config"] = handle_telegram_save
    routes["POST /api/telegram/detect-ids"] = handle_telegram_detect
    routes["POST /api/telegram/verify-token"] = handle_telegram_verify
    routes["POST /api/fireflies/save-key"] = handle_fireflies_save
    routes["POST /api/clockify/save-key"] = handle_clockify_save
    routes["POST /api/slack/save-token"] = handle_slack_save
    routes["POST /api/slack/save-config"] = handle_slack_save_config
    routes["POST /api/slack/test-connection"] = handle_slack_test
    routes["GET /api/slack/list-conversations"] = handle_slack_list_conversations
    routes["GET /api/health"] = handle_health_all
    routes["POST /api/shutdown"] = handle_shutdown


# ---------------------------------------------------------------------------
# Status / prerequisites
# ---------------------------------------------------------------------------


def handle_status(_body, _headers) -> dict:
    return state.as_dict()


def handle_prerequisites(_body, _headers) -> dict:
    venv_python = (
        REPO_ROOT
        / ".venv"
        / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    )
    return {
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "venv_exists": venv_python.exists(),
        "secrets_dir_exists": SECRETS_DIR.exists(),
        "repo_root": str(REPO_ROOT),
        "assistant": agent_cli.detect(),
    }


def handle_assistant_status(_body, _headers) -> dict:
    return agent_cli.detect()


def handle_assistant_install(_body, _headers) -> dict:
    return agent_cli.install_default()


def handle_assistant_launch(body, _headers) -> dict:
    key = body.get("assistant", "")
    return agent_cli.launch(key)


# ---------------------------------------------------------------------------
# Google
# ---------------------------------------------------------------------------


def handle_google_upload(body, _headers) -> dict:
    client_json = body.get("client_json", "")
    accounts = body.get("accounts", ["private"])

    fmt = validators.format_check_google_client(client_json)
    if not fmt["valid"]:
        return fmt

    result = google_auth_helper.save_oauth_client(
        client_json.encode("utf-8"),
        ["gcal", "gmail"],
        accounts,
    )
    current = state.load()
    current.google_credentials_uploaded = True
    current.google_accounts = accounts
    state.save(current)
    return result


def handle_google_start_auth(body, _headers) -> dict:
    service = body.get("service", "")
    account = body.get("account", "private")
    result = google_auth_helper.run_oauth_flow(service, account)
    if result.get("success"):
        current = state.load()
        attr = f"{service}_{account}_authed"
        if hasattr(current, attr):
            setattr(current, attr, True)
        state.save(current)
    return result


def handle_google_auth_status(_body, _headers) -> dict:
    current = state.load()
    return {
        "gcal_private_authed": current.gcal_private_authed,
        "gcal_personal_authed": current.gcal_personal_authed,
        "gmail_private_authed": current.gmail_private_authed,
        "gmail_personal_authed": current.gmail_personal_authed,
        "google_credentials_uploaded": current.google_credentials_uploaded,
        "google_accounts": current.google_accounts,
    }


# ---------------------------------------------------------------------------
# Todoist
# ---------------------------------------------------------------------------


def handle_todoist_save(body, _headers) -> dict:
    token = body.get("token", "")
    result = validators.live_check_todoist(token)
    if result["valid"]:
        clean_token = result.get("token", token.strip())
        token_path = SECRETS_DIR / "todoist_token_personal.json"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(
            json.dumps({"token": clean_token}, indent=2),
            encoding="utf-8",
        )
        current = state.load()
        current.todoist_connected = True
        state.save(current)
    return result


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------


def handle_telegram_verify(body, _headers) -> dict:
    token = body.get("bot_token", "")
    return validators.live_check_telegram(token)


def handle_telegram_detect(body, _headers) -> dict:
    token = body.get("bot_token", "")
    return validators.detect_telegram_ids(token)


def handle_telegram_save(body, _headers) -> dict:
    bot_token = body.get("bot_token", "")
    user_id = body.get("user_id", "")
    chat_id = body.get("chat_id", "")

    fmt = validators.format_check_telegram(bot_token)
    if not fmt["valid"]:
        return fmt

    env_path = SECRETS_DIR / "telegram_bridge.env"
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_content = (
        f"TELEGRAM_BOT_TOKEN={bot_token.strip()}\n"
        f"TELEGRAM_ALLOWED_USER_IDS={user_id}\n"
        f"TELEGRAM_ALLOWED_CHAT_IDS={chat_id}\n"
        f"VAULT_ROOT={REPO_ROOT}\n"
    )
    env_path.write_text(env_content, encoding="utf-8")

    current = state.load()
    current.telegram_connected = True
    state.save(current)

    return {"valid": True, "message": "Telegram bridge configured."}


# ---------------------------------------------------------------------------
# Fireflies
# ---------------------------------------------------------------------------


def handle_fireflies_save(body, _headers) -> dict:
    key = body.get("key", "")
    result = validators.live_check_fireflies(key)
    if result["valid"]:
        key_path = SECRETS_DIR / "fireflies_api_key.txt"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(key.strip(), encoding="utf-8")
        current = state.load()
        current.fireflies_connected = True
        state.save(current)
    return result


# ---------------------------------------------------------------------------
# Clockify
# ---------------------------------------------------------------------------


def handle_clockify_save(body, _headers) -> dict:
    key = body.get("key", "")
    result = validators.live_check_clockify(key)
    if result["valid"]:
        key_path = SECRETS_DIR / "clockify_token.txt"
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(key.strip(), encoding="utf-8")
        current = state.load()
        current.clockify_connected = True
        state.save(current)
    return result


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------


def handle_slack_save(body, _headers) -> dict:
    token = body.get("token", "")
    alias = body.get("alias", "private")
    result = validators.live_check_slack(token)
    if result["valid"]:
        token_path = SECRETS_DIR / f"slack_token_{alias}.txt"
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(token.strip(), encoding="utf-8")
        current = state.load()
        current.slack_connected = True
        if alias not in current.slack_workspaces:
            current.slack_workspaces.append(alias)
        state.save(current)
    return result


def handle_slack_test(body, _headers) -> dict:
    token = body.get("token", "")
    return validators.live_check_slack(token)


def handle_slack_list_conversations(_body, _headers) -> dict:
    current = state.load()
    if not current.slack_workspaces:
        return {"ok": False, "error": "No Slack workspace configured yet."}
    alias = current.slack_workspaces[0]
    token_path = SECRETS_DIR / f"slack_token_{alias}.txt"
    if not token_path.exists():
        return {"ok": False, "error": f"Token file not found: {token_path.name}"}
    token = token_path.read_text(encoding="utf-8").strip()
    return validators.list_slack_conversations(token)


def handle_slack_save_config(body, _headers) -> dict:
    config = body.get("config", {})
    config_path = INTEGRATIONS_DIR / "slack" / "workspaces.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {"saved": True, "path": str(config_path)}


# ---------------------------------------------------------------------------
# Health / shutdown
# ---------------------------------------------------------------------------


def handle_health_all(_body, _headers) -> dict:
    return state.as_dict()


def handle_shutdown(_body, _headers) -> dict:
    from . import server as srv

    ref = srv.get_server_ref()
    if ref:
        threading.Timer(0.5, ref.shutdown).start()
    return {"message": "Wizard shutting down."}
