"""Wizard progress state -- tracks which services are configured."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path

WIZARD_DIR = Path(__file__).resolve().parent
STATE_FILE = WIZARD_DIR.parent / "wizard_state.json"
REPO_ROOT = WIZARD_DIR.parent.parent
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"
INTEGRATIONS_DIR = REPO_ROOT / "90_System" / "Integrations"
PLAYWRIGHT_PLUGIN_ROOT = Path.home() / "plugins" / "playwright-browser"
PLAYWRIGHT_PLUGIN_FILES = (
    PLAYWRIGHT_PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
    PLAYWRIGHT_PLUGIN_ROOT / ".mcp.json",
    PLAYWRIGHT_PLUGIN_ROOT / "scripts" / "server.mjs",
)


@dataclass
class WizardState:
    google_credentials_uploaded: bool = False
    google_accounts: list[str] = field(default_factory=list)
    gcal_private_authed: bool = False
    gcal_personal_authed: bool = False
    gmail_private_authed: bool = False
    gmail_personal_authed: bool = False
    gdrive_private_authed: bool = False
    gdrive_personal_authed: bool = False
    todoist_connected: bool = False
    telegram_connected: bool = False
    fireflies_connected: bool = False
    clockify_connected: bool = False
    slack_connected: bool = False
    browser_playwright_installed: bool = False
    slack_workspaces: list[str] = field(default_factory=list)
    completed_at: str | None = None


SECRET_FILE_MAP: dict[str, tuple[str, bool]] = {
    "gcal_oauth_client_private.json": ("google_credentials_uploaded", True),
    "gcal_oauth_client_personal.json": ("google_credentials_uploaded", True),
    "gcal_oauth_client.json": ("google_credentials_uploaded", True),
    "gmail_oauth_client_private.json": ("google_credentials_uploaded", True),
    "gmail_oauth_client_personal.json": ("google_credentials_uploaded", True),
    "gmail_oauth_client.json": ("google_credentials_uploaded", True),
    "gdrive_oauth_client_private.json": ("google_credentials_uploaded", True),
    "gdrive_oauth_client_personal.json": ("google_credentials_uploaded", True),
    "gdrive_oauth_client.json": ("google_credentials_uploaded", True),
    "gcal_token_private.json": ("gcal_private_authed", True),
    "gcal_token_personal.json": ("gcal_personal_authed", True),
    "gmail_token_private.json": ("gmail_private_authed", True),
    "gmail_token_personal.json": ("gmail_personal_authed", True),
    "gdrive_token_private.json": ("gdrive_private_authed", True),
    "gdrive_token_personal.json": ("gdrive_personal_authed", True),
    "todoist_token_personal.json": ("todoist_connected", True),
    "telegram_bridge.env": ("telegram_connected", True),
    "fireflies_api_key.txt": ("fireflies_connected", True),
    "clockify_token.txt": ("clockify_connected", True),
    "slack_token_private.txt": ("slack_connected", True),
}


def _auto_detect(state: WizardState) -> WizardState:
    for filename, (attr, value) in SECRET_FILE_MAP.items():
        if (SECRETS_DIR / filename).exists():
            setattr(state, attr, value)

    for account in ("private", "personal"):
        if (
            (SECRETS_DIR / f"gcal_oauth_client_{account}.json").exists()
            or (SECRETS_DIR / f"gmail_oauth_client_{account}.json").exists()
            or (SECRETS_DIR / f"gdrive_oauth_client_{account}.json").exists()
        ):
            if account not in state.google_accounts:
                state.google_accounts.append(account)

    if not state.google_accounts and (
        (SECRETS_DIR / "gcal_oauth_client.json").exists()
        or (SECRETS_DIR / "gmail_oauth_client.json").exists()
        or (SECRETS_DIR / "gdrive_oauth_client.json").exists()
    ):
        state.google_accounts.append("private")

    if (SECRETS_DIR / "slack_token_private.txt").exists():
        if "private" not in state.slack_workspaces:
            state.slack_workspaces.append("private")

    if all(path.exists() for path in PLAYWRIGHT_PLUGIN_FILES):
        state.browser_playwright_installed = True

    return state


def load() -> WizardState:
    state = WizardState()
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            for key, value in data.items():
                if hasattr(state, key):
                    setattr(state, key, value)
        except (json.JSONDecodeError, OSError):
            pass
    return _auto_detect(state)


def save(state: WizardState) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(dataclasses.asdict(state), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def as_dict() -> dict:
    return dataclasses.asdict(load())
