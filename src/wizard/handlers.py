"""API endpoint handlers -- all routes that the wizard frontend calls."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path

from . import agent_cli, google_auth_helper, state, validators

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
INTEGRATIONS_DIR = REPO_ROOT / "90_System" / "Integrations"


def register_routes(routes: dict) -> None:
    routes["GET /api/status"] = handle_status
    routes["GET /api/prerequisites"] = handle_prerequisites
    routes["GET /api/assistant/status"] = handle_assistant_status
    routes["POST /api/assistant/install"] = handle_assistant_install
    routes["POST /api/assistant/launch"] = handle_assistant_launch
    routes["GET /api/browser/status"] = handle_browser_status
    routes["POST /api/browser/install"] = handle_browser_install
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
    routes["POST /api/initial-load/run"] = handle_initial_load_run
    routes["GET /api/health"] = handle_health_all
    routes["POST /api/shutdown"] = handle_shutdown


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


def handle_assistant_install(body, _headers) -> dict:
    key = body.get("assistant", "codex")
    return agent_cli.install(key)


def handle_assistant_launch(body, _headers) -> dict:
    key = body.get("assistant", "")
    return agent_cli.launch(key)


def handle_browser_status(_body, _headers) -> dict:
    current = state.load()
    return {
        "supported": sys.platform in {"win32", "darwin"},
        "platform": "windows"
        if sys.platform == "win32"
        else "macos"
        if sys.platform == "darwin"
        else sys.platform,
        "installed": current.browser_playwright_installed,
        "plugin_root": str(state.PLAYWRIGHT_PLUGIN_ROOT),
    }


def handle_browser_install(_body, _headers) -> dict:
    if sys.platform not in {"win32", "darwin"}:
        return {
            "ok": False,
            "message": "Playwright Browser installer is currently only available on Windows and macOS.",
            "status": handle_browser_status(None, None),
        }

    installer_name = (
        "install_playwright_browser_plugin.ps1"
        if sys.platform == "win32"
        else "install_playwright_browser_plugin.sh"
    )
    installer = (
        REPO_ROOT / "90_System" / "Skills" / "browser_playwright" / installer_name
    )
    if not installer.exists():
        return {
            "ok": False,
            "message": f"Installer not found: {installer}",
            "status": handle_browser_status(None, None),
        }

    try:
        command = (
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(installer),
            ]
            if sys.platform == "win32"
            else ["bash", str(installer)]
        )
        result = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=1800,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return {
            "ok": False,
            "message": f"Playwright Browser install failed: {detail}",
            "status": handle_browser_status(None, None),
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Playwright Browser install failed: {exc}",
            "status": handle_browser_status(None, None),
        }

    refreshed_status = handle_browser_status(None, None)
    output = (result.stdout or "").strip()
    message = "Installed Playwright Browser plugin and Chromium."
    if not refreshed_status.get("installed"):
        message = "Playwright Browser installer finished, but the plugin files were not detected."
    if output:
        message = f"{message} {output.splitlines()[-1]}"
    return {
        "ok": bool(refreshed_status.get("installed")),
        "message": message,
        "status": refreshed_status,
    }


def handle_google_upload(body, _headers) -> dict:
    credentials = body.get("credentials", [])
    if not credentials:
        return {
            "valid": False,
            "message": "Upload at least one Google OAuth client JSON file.",
        }

    normalized = []
    accounts = []
    for item in credentials:
        account = item.get("account", "").strip()
        client_json = item.get("client_json", "")
        if account not in {"private", "personal"}:
            return {
                "valid": False,
                "message": f"Unsupported Google account key: {account}",
            }
        fmt = validators.format_check_google_client(client_json)
        if not fmt["valid"]:
            return fmt
        normalized.append({"account": account, "client_json": client_json})
        accounts.append(account)

    result = google_auth_helper.save_oauth_clients(normalized)
    current = state.load()
    current.google_credentials_uploaded = True
    current.google_accounts = sorted(
        set(accounts), key=lambda item: ["private", "personal"].index(item)
    )
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
        "gdrive_private_authed": current.gdrive_private_authed,
        "gdrive_personal_authed": current.gdrive_personal_authed,
        "google_credentials_uploaded": current.google_credentials_uploaded,
        "google_accounts": current.google_accounts,
    }


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


def handle_slack_save_config(body, _headers) -> dict:
    config = body.get("config", {})
    config_path = INTEGRATIONS_DIR / "slack" / "workspaces.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return {"saved": True, "path": str(config_path)}


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


def _selected_google_accounts(current: state.WizardState, service_prefix: str) -> list[str]:
    accounts = []
    for account in current.google_accounts or ["private"]:
        if getattr(current, f"{service_prefix}_{account}_authed", False):
            accounts.append(account)
    return accounts


def _venv_python() -> Path:
    return REPO_ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def _run_initial_load_command(args: list[str], timeout: int = 1800) -> dict:
    proc = subprocess.run(
        [str(_venv_python()), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return {
        "ok": proc.returncode == 0,
        "command": " ".join(args),
        "stdout": (proc.stdout or "").strip(),
        "stderr": (proc.stderr or "").strip(),
        "returncode": proc.returncode,
    }


def handle_initial_load_run(body, _headers) -> dict:
    services = body.get("services", [])
    days_back = int(body.get("days_back", 7) or 7)
    todoist_days_ahead = int(body.get("todoist_days_ahead", days_back) or days_back)
    if days_back < 1:
        return {"ok": False, "message": "days_back must be >= 1"}
    if todoist_days_ahead < 0:
        return {"ok": False, "message": "todoist_days_ahead must be >= 0"}

    current = state.load()
    gcal_accounts = _selected_google_accounts(current, "gcal")
    gmail_accounts = _selected_google_accounts(current, "gmail")

    commands: list[tuple[str, list[str], int]] = []
    if "meetings" in services and gcal_accounts:
        commands.append((
            "Meetings",
            [
                "90_System/Skills/gcal_today/gcal_today.py",
                "sync",
                "--days-back",
                str(days_back),
                "--accounts",
                *gcal_accounts,
            ],
            1800,
        ))
    if "emails" in services and gmail_accounts:
        commands.append((
            "Emails",
            [
                "90_System/Skills/process_emails/process_emails.py",
                "sync",
                "--days-back",
                str(days_back),
                "--accounts",
                *gmail_accounts,
            ],
            1800,
        ))
    if "messages" in services and current.slack_connected:
        commands.append((
            "Slack messages",
            ["90_System/Skills/process_slack/process_slack.py", "sync", "--days-back", str(days_back)],
            2400,
        ))
    if "tasks" in services and current.todoist_connected:
        commands.append((
            "Todoist tasks",
            ["90_System/Skills/daily_brief_todoist/daily_brief_todoist.py", "sync", "--days-ahead", str(todoist_days_ahead)],
            1800,
        ))

    if not commands:
        return {"ok": True, "message": "No initial load services selected.", "results": []}

    results = []
    overall_ok = True
    for label, cmd, timeout in commands:
        result = _run_initial_load_command(cmd, timeout=timeout)
        result["label"] = label
        results.append(result)
        if not result["ok"]:
            overall_ok = False

    return {
        "ok": overall_ok,
        "message": "Initial load finished." if overall_ok else "Initial load finished with errors.",
        "results": results,
    }


def handle_health_all(_body, _headers) -> dict:
    return state.as_dict()


def handle_shutdown(_body, _headers) -> dict:
    from . import server as srv

    ref = srv.get_server_ref()
    if ref:
        threading.Timer(0.5, ref.shutdown).start()
    return {"message": "Wizard shutting down."}
