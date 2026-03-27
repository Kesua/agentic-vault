"""Token format checks and live API validation for each service.

All network calls use urllib.request (stdlib) -- no requests library.
Each service exposes format_check_<service>() and live_check_<service>().
Both return {"valid": bool, "message": str, ...extra_fields}.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

def _make_request(
    url: str,
    headers: dict = None,
    data: bytes = None,
    method: str = "GET",
    auth_error_msg: str = "Token rejected.",
    api_name: str = "API",
    timeout: int = 15
) -> tuple[bool, dict, str]:
    """Helper for JSON-based HTTP requests to reduce boilerplate."""
    try:
        req = urllib.request.Request(url, headers=headers or {}, data=data, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, json.loads(resp.read()), ""
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return False, {}, auth_error_msg
        return False, {}, f"{api_name} error: HTTP {exc.code}"
    except Exception as exc:
        return False, {}, f"Could not reach {api_name}: {exc}"

# ---------------------------------------------------------------------------
# Todoist
# ---------------------------------------------------------------------------

def format_check_todoist(token: str) -> dict:
    token = token.strip()
    if token.startswith("{"):
        try:
            parsed = json.loads(token)
            token = parsed.get("token", "")
        except json.JSONDecodeError:
            return {"valid": False, "message": "Invalid JSON format"}
    if not token or len(token) < 10:
        return {"valid": False, "message": "Token is too short"}
    return {"valid": True, "message": "Format OK", "token": token}


def live_check_todoist(token: str) -> dict:
    fmt = format_check_todoist(token)
    if not fmt["valid"]:
        return fmt
    clean_token = fmt.get("token", token.strip())
    
    ok, data, err = _make_request(
        "https://api.todoist.com/api/v1/projects",
        headers={"Authorization": f"Bearer {clean_token}"},
        auth_error_msg="Token rejected by Todoist. Check and try again.",
        api_name="Todoist API"
    )
    if ok:
        return {"valid": True, "message": f"Connected! Found {len(data)} projects.", "token": clean_token}
    return {"valid": False, "message": err}


# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------

_TELEGRAM_TOKEN_RE = re.compile(r"^\d{8,10}:[A-Za-z0-9_-]{35,}$")


def format_check_telegram(token: str) -> dict:
    token = token.strip()
    if not _TELEGRAM_TOKEN_RE.match(token):
        return {
            "valid": False,
            "message": "Token format incorrect. Expected: 123456789:ABCdef... (from @BotFather)",
        }
    return {"valid": True, "message": "Format OK", "token": token}


def live_check_telegram(token: str) -> dict:
    fmt = format_check_telegram(token)
    if not fmt["valid"]:
        return fmt
    clean_token = token.strip()

    ok, data, err = _make_request(
        f"https://api.telegram.org/bot{clean_token}/getMe",
        auth_error_msg="Telegram rejected this token.",
        api_name="Telegram API"
    )
    if ok and data.get("ok"):
        bot_name = data["result"].get("username", "unknown")
        return {"valid": True, "message": f"Bot verified: @{bot_name}", "token": clean_token}
    return {"valid": False, "message": err or "Telegram rejected this token."}


def detect_telegram_ids(token: str) -> dict:
    """Call getUpdates to find user_id and chat_id from the most recent message."""
    ok, data, err = _make_request(
        f"https://api.telegram.org/bot{token.strip()}/getUpdates?offset=-1&limit=5",
        api_name="Telegram API"
    )
    if not ok:
        return {"found": False, "message": err.replace("API error:", "Error calling getUpdates:")}
    if not data.get("ok") or not data.get("result"):
        return {"found": False, "message": "No messages found. Send a message to your bot first."}
    
    for update in reversed(data["result"]):
        msg = update.get("message", {})
        user = msg.get("from", {})
        chat = msg.get("chat", {})
        if user.get("id") and chat.get("id"):
            return {
                "found": True,
                "user_id": user["id"],
                "chat_id": chat["id"],
                "username": user.get("username", ""),
                "first_name": user.get("first_name", ""),
            }
    return {"found": False, "message": "Messages found but no user info. Try sending /start to the bot."}


# ---------------------------------------------------------------------------
# Fireflies
# ---------------------------------------------------------------------------

def format_check_fireflies(key: str) -> dict:
    key = key.strip()
    if not key or len(key) < 10:
        return {"valid": False, "message": "API key is too short"}
    return {"valid": True, "message": "Format OK", "key": key}


def live_check_fireflies(key: str) -> dict:
    fmt = format_check_fireflies(key)
    if not fmt["valid"]:
        return fmt
    clean_key = key.strip()

    ok, data, err = _make_request(
        "https://api.fireflies.ai/graphql",
        headers={"Authorization": f"Bearer {clean_key}", "Content-Type": "application/json"},
        data=json.dumps({"query": "{ user { email } }"}).encode("utf-8"),
        method="POST",
        auth_error_msg="API key rejected by Fireflies.",
        api_name="Fireflies API"
    )
    if ok:
        email = data.get("data", {}).get("user", {}).get("email", "unknown")
        return {"valid": True, "message": f"Connected as {email}", "key": clean_key}
    return {"valid": False, "message": err}


# ---------------------------------------------------------------------------
# Clockify
# ---------------------------------------------------------------------------

def format_check_clockify(key: str) -> dict:
    key = key.strip()
    if not key or len(key) < 10:
        return {"valid": False, "message": "API key is too short"}
    return {"valid": True, "message": "Format OK", "key": key}


def live_check_clockify(key: str) -> dict:
    fmt = format_check_clockify(key)
    if not fmt["valid"]:
        return fmt
    clean_key = key.strip()

    ok, data, err = _make_request(
        "https://api.clockify.me/api/v1/user",
        headers={"X-Api-Key": clean_key},
        auth_error_msg="API key rejected by Clockify.",
        api_name="Clockify API"
    )
    if ok:
        name = data.get("name", "unknown")
        email = data.get("email", "")
        label = f"{name} ({email})" if email else name
        return {"valid": True, "message": f"Connected as {label}", "key": clean_key}
    return {"valid": False, "message": err}


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

def format_check_slack(token: str) -> dict:
    token = token.strip()
    if not (token.startswith("xoxb-") or token.startswith("xoxe.xoxb-")):
        return {
            "valid": False,
            "message": "Slack bot token should start with 'xoxb-' or 'xoxe.xoxb-'",
        }
    return {"valid": True, "message": "Format OK", "token": token}


def live_check_slack(token: str) -> dict:
    fmt = format_check_slack(token)
    if not fmt["valid"]:
        return fmt
    clean_token = token.strip()

    ok, data, err = _make_request(
        "https://slack.com/api/auth.test",
        headers={"Authorization": f"Bearer {clean_token}"},
        data=b"",
        method="POST",
        api_name="Slack"
    )
    if ok and data.get("ok"):
        return {
            "valid": True,
            "message": f"Connected to workspace: {data.get('team', 'unknown')}",
            "team_id": data.get("team_id"),
            "user_id": data.get("user_id"),
            "team": data.get("team"),
            "token": clean_token,
        }
    return {"valid": False, "message": err or f"Slack error: {data.get('error', 'unknown')}"}


def list_slack_conversations(token: str) -> dict:
    """Fetch public and private channels the bot can see."""
    ok, data, err = _make_request(
        "https://slack.com/api/conversations.list?types=public_channel,private_channel,im&limit=200",
        headers={"Authorization": f"Bearer {token.strip()}"},
        api_name="Slack"
    )
    if ok and data.get("ok"):
        channels = [
            {
                "id": ch["id"],
                "name": ch.get("name", ch.get("user", "dm")),
                "type": _channel_type(ch),
                "is_member": ch.get("is_member", False),
            }
            for ch in data.get("channels", [])
        ]
        return {"ok": True, "channels": channels}
    return {"ok": False, "error": err or data.get("error", "unknown")}


def _channel_type(ch: dict) -> str:
    if ch.get("is_im"):
        return "im"
    if ch.get("is_mpim"):
        return "mpim"
    if ch.get("is_private"):
        return "private_channel"
    return "public_channel"


# ---------------------------------------------------------------------------
# Google (format only -- live checks happen after OAuth)
# ---------------------------------------------------------------------------

def format_check_google_client(client_json_str: str) -> dict:
    """Validate that the uploaded JSON is a valid OAuth client config."""
    try:
        data = json.loads(client_json_str)
    except json.JSONDecodeError:
        return {"valid": False, "message": "File is not valid JSON"}

    installed = data.get("installed", {})
    if not installed.get("client_id"):
        return {"valid": False, "message": "Missing 'installed.client_id' -- is this a Desktop app credential?"}
    if not installed.get("client_secret"):
        return {"valid": False, "message": "Missing 'installed.client_secret'"}
    if not installed.get("redirect_uris"):
        return {"valid": False, "message": "Missing 'installed.redirect_uris'"}

    return {
        "valid": True,
        "message": "Valid OAuth client configuration",
        "project_id": installed.get("project_id", "unknown"),
        "client_id": installed["client_id"],
    }
