"""Google OAuth helper for the setup wizard.

One uploaded Desktop OAuth client JSON per account is reused for Calendar,
Gmail, and Google Workspace/Drive. The wizard materializes service-specific
client files so repo-local skills can keep their existing file contracts.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SECRETS_DIR = REPO_ROOT / "90_System" / "secrets"

SCOPES = {
    "gcal": ["https://www.googleapis.com/auth/calendar.readonly"],
    "gmail": [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.compose",
    ],
    "gdrive": [
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/documents",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/presentations",
    ],
}

SERVICES = ["gcal", "gmail", "gdrive"]


def save_oauth_clients(credentials: list[dict]) -> dict:
    """Save one uploaded Desktop OAuth client JSON per account.

    Each provided account JSON is copied into gcal/gmail/gdrive service-specific
    client files. When exactly one account is provided, shared fallback files
    without the account suffix are also written for compatibility.
    """

    saved_files: list[str] = []
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    normalized: list[tuple[str, dict]] = []
    for item in credentials:
        account = item.get("account", "").strip()
        raw_json = item.get("client_json", "")
        parsed = json.loads(raw_json)
        normalized.append((account, parsed))

    for account, parsed in normalized:
        for service in SERVICES:
            path = SECRETS_DIR / f"{service}_oauth_client_{account}.json"
            path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            saved_files.append(str(path))

    if len(normalized) == 1:
        _, parsed = normalized[0]
        for service in SERVICES:
            path = SECRETS_DIR / f"{service}_oauth_client.json"
            path.write_text(json.dumps(parsed, indent=2), encoding="utf-8")
            saved_files.append(str(path))

    return {
        "saved_files": saved_files,
        "valid": True,
        "message": f"Saved {len(saved_files)} Google credential files.",
    }


def run_oauth_flow(service: str, account: str) -> dict:
    scopes = SCOPES.get(service)
    if not scopes:
        return {"success": False, "error": f"Unknown service: {service}"}

    client_path = _find_client_file(service, account)
    if not client_path:
        return {
            "success": False,
            "error": f"OAuth client file not found for {service}/{account}",
        }

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
                "Run the setup bootstrap again so dependencies are installed."
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
