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
    try:
        req = urllib.request.Request(
            "https://api.todoist.com/api/v1/projects",
            headers={"Authorization": f"Bearer {clean_token}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            projects = json.loads(resp.read())
            return {
                "valid": True,
                "message": f"Connected! Found {len(projects)} projects.",
                "token": clean_token,
            }
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return {"valid": False, "message": "Token rejected by Todoist. Check and try again."}
        return {"valid": False, "message": f"Todoist API error: HTTP {exc.code}"}
    except Exception as exc:
        return {"valid": False, "message": f"Could not reach Todoist: {exc}"}


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
    try:
        url = f"https://api.telegram.org/bot{token.strip()}/getMe"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                bot_name = data["result"].get("username", "unknown")
                return {"valid": True, "message": f"Bot verified: @{bot_name}", "token": token.strip()}
            return {"valid": False, "message": "Telegram rejected this token."}
    except Exception as exc:
        return {"valid": False, "message": f"Could not reach Telegram: {exc}"}


def detect_telegram_ids(token: str) -> dict:
    """Call getUpdates to find user_id and chat_id from the most recent message."""
    try:
        url = f"https://api.telegram.org/bot{token.strip()}/getUpdates?offset=-1&limit=5"
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read())
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
    except Exception as exc:
        return {"found": False, "message": f"Error calling getUpdates: {exc}"}


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
    try:
        payload = json.dumps({"query": "{ user { email } }"}).encode("utf-8")
        req = urllib.request.Request(
            "https://api.fireflies.ai/graphql",
            data=payload,
            headers={
                "Authorization": f"Bearer {key.strip()}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            email = data.get("data", {}).get("user", {}).get("email", "unknown")
            return {"valid": True, "message": f"Connected as {email}", "key": key.strip()}
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return {"valid": False, "message": "API key rejected by Fireflies."}
        return {"valid": False, "message": f"Fireflies API error: HTTP {exc.code}"}
    except Exception as exc:
        return {"valid": False, "message": f"Could not reach Fireflies: {exc}"}


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
    try:
        req = urllib.request.Request(
            "https://api.clockify.me/api/v1/user",
            headers={"X-Api-Key": key.strip()},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            name = data.get("name", "unknown")
            email = data.get("email", "")
            label = f"{name} ({email})" if email else name
            return {"valid": True, "message": f"Connected as {label}", "key": key.strip()}
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return {"valid": False, "message": "API key rejected by Clockify."}
        return {"valid": False, "message": f"Clockify API error: HTTP {exc.code}"}
    except Exception as exc:
        return {"valid": False, "message": f"Could not reach Clockify: {exc}"}


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
    try:
        req = urllib.request.Request(
            "https://slack.com/api/auth.test",
            headers={"Authorization": f"Bearer {token.strip()}"},
            data=b"",
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                return {
                    "valid": True,
                    "message": f"Connected to workspace: {data.get('team', 'unknown')}",
                    "team_id": data.get("team_id"),
                    "user_id": data.get("user_id"),
                    "team": data.get("team"),
                    "token": token.strip(),
                }
            return {"valid": False, "message": f"Slack error: {data.get('error', 'unknown')}"}
    except Exception as exc:
        return {"valid": False, "message": f"Could not reach Slack: {exc}"}


def list_slack_conversations(token: str) -> dict:
    """Fetch public and private channels the bot can see."""
    try:
        url = "https://slack.com/api/conversations.list?types=public_channel,private_channel,im&limit=200"
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token.strip()}"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
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
            return {"ok": False, "error": data.get("error", "unknown")}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


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
