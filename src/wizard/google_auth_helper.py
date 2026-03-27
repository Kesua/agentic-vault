"""Google OAuth helper -- wraps InstalledAppFlow for wizard-triggered auth.

Reuses the same secret-file layout that gcal_today.py and gmail_assistant.py
expect so that existing skills work without changes after the wizard runs.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"

SCOPES = {
    "gcal": ["https://www.googleapis.com/auth/calendar.readonly"],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ],
}


def save_oauth_client(
    file_bytes: bytes,
    services: list[str],
    accounts: list[str],
) -> dict:
    """Save the OAuth client JSON to the correct paths for each service/account."""
    parsed = json.loads(file_bytes)
    saved_files: list[str] = []

    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    for service in services:
        if len(accounts) == 1 and accounts[0] in ("private", "personal"):
            for suffix in [f"_{accounts[0]}", ""]:
                path = SECRETS_DIR / f"{service}_oauth_client{suffix}.json"
                path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
                saved_files.append(str(path))
        else:
            for account in accounts:
                path = SECRETS_DIR / f"{service}_oauth_client_{account}.json"
                path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
                saved_files.append(str(path))

    return {
        "saved_files": saved_files,
        "valid": True,
        "message": f"Saved {len(saved_files)} credential files.",
    }


def run_oauth_flow(service: str, account: str) -> dict:
    """Run InstalledAppFlow for the given service + account.

    Opens a browser tab for Google sign-in and blocks until the user
    completes the consent flow or closes the window.
    """
    scopes = SCOPES.get(service)
    if not scopes:
        return {"success": False, "error": f"Unknown service: {service}"}

    client_path = _find_client_file(service, account)
    if not client_path:
        return {"success": False, "error": f"OAuth client file not found for {service}/{account}"}

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        flow = InstalledAppFlow.from_client_secrets_file(str(client_path), scopes)
        creds = flow.run_local_server(port=0)

        token_path = SECRETS_DIR / f"{service}_token_{account}.json"
        token_path.write_text(creds.to_json(), encoding="utf-8")

        return {
            "success": True,
            "service": service,
            "account": account,
            "token_path": str(token_path),
        }
    except ImportError:
        return {
            "success": False,
            "error": (
                "google-auth-oauthlib is not installed. "
                "Run: pip install google-auth-oauthlib"
            ),
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


def _find_client_file(service: str, account: str) -> Path | None:
    candidates = [
        SECRETS_DIR / f"{service}_oauth_client_{account}.json",
        SECRETS_DIR / f"{service}_oauth_client.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None
