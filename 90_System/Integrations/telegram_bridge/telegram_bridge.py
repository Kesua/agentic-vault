from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, parse, request


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_VAULT_ROOT = REPO_ROOT
DEFAULT_LOG_DIR = REPO_ROOT / "90_System" / "Logs" / "telegram_bridge"
DEFAULT_RUNTIME_DIR = (
    REPO_ROOT / "90_System" / "Integrations" / "telegram_bridge" / "runtime"
)
DEFAULT_TIMEOUT_SECONDS = 600
DEFAULT_POLL_TIMEOUT_SECONDS = 30
TELEGRAM_API_BASE = "https://api.telegram.org"
UNSUPPORTED_MESSAGE_TEXT = (
    "Tato verze bridge podporuje jen textove zpravy. Posli prosim text."
)
BUSY_TEXT = "Prave bezi jina uloha. Pockej na dokonceni a zkus to znovu."


@dataclass(frozen=True)
class BridgeConfig:
    bot_token: str
    allowed_user_ids: set[int]
    allowed_chat_ids: set[int]
    codex_command: str
    vault_root: Path
    log_dir: Path
    runtime_dir: Path
    timeout_seconds: int
    poll_timeout_seconds: int
    accept_plain_text: bool


class BridgeError(RuntimeError):
    """Raised for bridge-level operational failures."""


@dataclass(frozen=True)
class SessionKey:
    user_id: int
    chat_id: int


def _load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Invalid config line: {raw_line}")
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _split_csv_ints(value: str | None) -> set[int]:
    if not value:
        return set()
    out: set[int] = set()
    for part in value.split(","):
        item = part.strip()
        if not item:
            continue
        out.add(int(item))
    return out


def _resolve_path(raw: str | None, default: Path) -> Path:
    if not raw:
        return default
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def _parse_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().casefold()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Invalid boolean value: {raw}")


def load_config(config_path: Path | None) -> BridgeConfig:
    env = dict(os.environ)
    if config_path is not None:
        env.update(_load_env_file(config_path))

    bot_token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise BridgeError("Missing TELEGRAM_BOT_TOKEN")

    allowed_user_ids = _split_csv_ints(env.get("TELEGRAM_ALLOWED_USER_IDS"))
    allowed_chat_ids = _split_csv_ints(env.get("TELEGRAM_ALLOWED_CHAT_IDS"))
    if not allowed_user_ids:
        raise BridgeError("Missing TELEGRAM_ALLOWED_USER_IDS")
    if not allowed_chat_ids:
        raise BridgeError("Missing TELEGRAM_ALLOWED_CHAT_IDS")

    codex_command = env.get("CODEX_COMMAND", "codex").strip() or "codex"
    vault_root = _resolve_path(env.get("VAULT_ROOT"), DEFAULT_VAULT_ROOT)
    log_dir = _resolve_path(env.get("BRIDGE_LOG_DIR"), DEFAULT_LOG_DIR)
    runtime_dir = _resolve_path(env.get("BRIDGE_RUNTIME_DIR"), DEFAULT_RUNTIME_DIR)
    timeout_seconds = int(env.get("BRIDGE_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    poll_timeout_seconds = int(
        env.get("BRIDGE_POLL_TIMEOUT_SECONDS", DEFAULT_POLL_TIMEOUT_SECONDS)
    )
    accept_plain_text = _parse_bool(env.get("BRIDGE_ACCEPT_PLAIN_TEXT"), True)

    if timeout_seconds <= 0 or poll_timeout_seconds <= 0:
        raise BridgeError("Timeouts must be positive integers")

    return BridgeConfig(
        bot_token=bot_token,
        allowed_user_ids=allowed_user_ids,
        allowed_chat_ids=allowed_chat_ids,
        codex_command=codex_command,
        vault_root=vault_root,
        log_dir=log_dir,
        runtime_dir=runtime_dir,
        timeout_seconds=timeout_seconds,
        poll_timeout_seconds=poll_timeout_seconds,
        accept_plain_text=accept_plain_text,
    )


def _ensure_dirs(config: BridgeConfig) -> None:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.runtime_dir.mkdir(parents=True, exist_ok=True)
    (config.runtime_dir / "sessions").mkdir(parents=True, exist_ok=True)


def _state_file(config: BridgeConfig) -> Path:
    return config.runtime_dir / "last_update_id.txt"


def _sessions_dir(config: BridgeConfig) -> Path:
    return config.runtime_dir / "sessions"


def _lock_file(config: BridgeConfig) -> Path:
    return config.runtime_dir / "bridge.lock"


def _last_run_file(config: BridgeConfig) -> Path:
    return config.runtime_dir / "last_run.json"


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _today_log_path(config: BridgeConfig) -> Path:
    return config.log_dir / f"{_now_local():%Y-%m-%d}.log"


def _append_log(config: BridgeConfig, level: str, message: str, **fields: Any) -> None:
    payload = {
        "ts": _now_local().isoformat(timespec="seconds"),
        "level": level,
        "message": message,
        **fields,
    }
    line = json.dumps(payload, ensure_ascii=False)
    with _today_log_path(config).open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def _session_path(config: BridgeConfig, key: SessionKey) -> Path:
    return _sessions_dir(config) / f"user_{key.user_id}__chat_{key.chat_id}.json"


def _session_key_from_message(message: dict[str, Any]) -> SessionKey | None:
    user_id = message.get("from", {}).get("id")
    chat_id = message.get("chat", {}).get("id")
    if not isinstance(user_id, int) or not isinstance(chat_id, int):
        return None
    return SessionKey(user_id=user_id, chat_id=chat_id)


def _new_session_payload(key: SessionKey) -> dict[str, Any]:
    now = _now_local().isoformat(timespec="seconds")
    return {
        "user_id": key.user_id,
        "chat_id": key.chat_id,
        "started_at": now,
        "updated_at": now,
        "turns": [],
    }


def _load_session(config: BridgeConfig, key: SessionKey) -> dict[str, Any]:
    path = _session_path(config, key)
    if not path.exists():
        return _new_session_payload(key)
    try:
        session = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _new_session_payload(key)
    if not isinstance(session, dict):
        return _new_session_payload(key)
    turns = session.get("turns")
    if not isinstance(turns, list):
        session["turns"] = []
    session["user_id"] = key.user_id
    session["chat_id"] = key.chat_id
    session.setdefault("started_at", _now_local().isoformat(timespec="seconds"))
    session["updated_at"] = _now_local().isoformat(timespec="seconds")
    return session


def _save_session(
    config: BridgeConfig, key: SessionKey, session: dict[str, Any]
) -> None:
    session["user_id"] = key.user_id
    session["chat_id"] = key.chat_id
    session["updated_at"] = _now_local().isoformat(timespec="seconds")
    _session_path(config, key).write_text(
        json.dumps(session, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _reset_session(config: BridgeConfig, key: SessionKey) -> dict[str, Any]:
    session = _new_session_payload(key)
    _save_session(config, key, session)
    return session


def _append_session_turn(
    config: BridgeConfig, key: SessionKey, role: str, text: str
) -> None:
    session = _load_session(config, key)
    turns = session.setdefault("turns", [])
    turns.append(
        {
            "role": role,
            "ts": _now_local().isoformat(timespec="seconds"),
            "text": text,
        }
    )
    _save_session(config, key, session)


def _format_session_history(session: dict[str, Any]) -> str:
    turns = session.get("turns")
    if not isinstance(turns, list) or not turns:
        return "(empty session)"
    lines: list[str] = []
    for turn in turns:
        if not isinstance(turn, dict):
            continue
        role = "Assistant" if turn.get("role") == "assistant" else "User"
        ts = turn.get("ts") or "n/a"
        text = str(turn.get("text") or "").strip()
        lines.append(f"{role} [{ts}]:")
        lines.append(text or "(empty)")
        lines.append("")
    return "\n".join(lines).strip() or "(empty session)"


def _context_limit_hint(text: str) -> bool:
    lowered = text.casefold()
    return any(
        needle in lowered
        for needle in (
            "context",
            "token limit",
            "too many tokens",
            "prompt is too long",
            "context length",
            "maximum context",
            "input is too long",
        )
    )


def _load_last_update_id(config: BridgeConfig) -> int | None:
    path = _state_file(config)
    if not path.exists():
        return None
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    return int(raw)


def _save_last_update_id(config: BridgeConfig, update_id: int) -> None:
    _state_file(config).write_text(str(update_id), encoding="utf-8")


def _write_last_run(config: BridgeConfig, payload: dict[str, Any]) -> None:
    _last_run_file(config).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _telegram_request(
    config: BridgeConfig, method: str, payload: dict[str, Any]
) -> Any:
    encoded = parse.urlencode(payload).encode("utf-8")
    req = request.Request(
        f"{TELEGRAM_API_BASE}/bot{config.bot_token}/{method}",
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=config.poll_timeout_seconds + 10) as response:
            body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise BridgeError(f"Telegram API HTTP {exc.code}: {detail[:500]}") from exc
    except error.URLError as exc:
        raise BridgeError(f"Telegram API request failed: {exc}") from exc

    try:
        parsed = json.loads(body)
    except json.JSONDecodeError as exc:
        raise BridgeError("Telegram API returned invalid JSON") from exc
    if not parsed.get("ok"):
        raise BridgeError(f"Telegram API error: {parsed}")
    return parsed.get("result")


def send_message(config: BridgeConfig, chat_id: int, text: str) -> None:
    _telegram_request(
        config,
        "sendMessage",
        {
            "chat_id": str(chat_id),
            "text": text[:4000],
        },
    )


def get_updates(config: BridgeConfig, offset: int | None) -> list[dict[str, Any]]:
    payload = {"timeout": str(config.poll_timeout_seconds)}
    if offset is not None:
        payload["offset"] = str(offset)
    result = _telegram_request(config, "getUpdates", payload)
    if not isinstance(result, list):
        raise BridgeError("Telegram API returned invalid updates payload")
    return result


def _extract_text(message: dict[str, Any]) -> tuple[str | None, str | None]:
    if "text" in message and isinstance(message["text"], str):
        return message["text"], "text"
    if any(
        key in message
        for key in ("voice", "audio", "video_note", "photo", "document", "sticker")
    ):
        return None, "unsupported"
    return None, "ignored"


def _safe_preview(text: str, limit: int = 200) -> str:
    compact = " ".join(text.split())
    return compact[:limit]


def _build_help_text() -> str:
    return "\n".join(
        [
            "Telegram bridge pro Codex CLI.",
            "",
            "Prikazy:",
            "/start - kratke uvedeni",
            "/help - napoveda",
            "/status - stav bridge a posledni uloha",
            "/run <dotaz> - spusti dotaz pres Codex",
            "",
            "/start zaroven smaze predchozi kontext a zahaji novou session pro tento chat a uzivatele.",
            "V1 podporuje jen textove zpravy.",
        ]
    )


def _build_start_text() -> str:
    return "\n".join(
        [
            "Bridge zahajil novou konverzacni session pro tento chat a uzivatele.",
            "Pouzij /run <dotaz> nebo posli prosty text, pokud je plain text povoleny.",
            "Dalsi dotazy a odpovedi se budou pamatovat az do dalsiho /start.",
            "V1 nepodporuje hlasove zpravy.",
        ]
    )


def _build_status_text(config: BridgeConfig) -> str:
    lock_active = _lock_file(config).exists()
    last_run = None
    if _last_run_file(config).exists():
        try:
            last_run = json.loads(_last_run_file(config).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            last_run = None

    lines = [
        f"Bridge stav: {'obsazeno' if lock_active else 'volno'}",
        f"Vault root: {config.vault_root}",
        f"Timeout: {config.timeout_seconds}s",
    ]
    if isinstance(last_run, dict):
        ended_at = last_run.get("ended_at") or "n/a"
        summary = last_run.get("summary") or "bez zaznamu"
        lines.append(f"Posledni beh: {ended_at}")
        lines.append(f"Posledni vysledek: {summary}")
    lines.append("Kontext po /start se pamatuje az do dalsiho /start.")
    return "\n".join(lines)


def _normalize_prompt(raw_text: str, accept_plain_text: bool) -> str | None:
    text = raw_text.strip()
    if not text:
        return None
    if text.startswith("/start"):
        return "__START__"
    if text.startswith("/help"):
        return "__HELP__"
    if text.startswith("/status"):
        return "__STATUS__"
    if text.startswith("/run"):
        prompt = text[4:].strip()
        return prompt or None
    if accept_plain_text:
        return text
    return None


def _build_codex_prompt(
    user_text: str, message: dict[str, Any], session: dict[str, Any]
) -> str:
    local_now = _now_local()
    lines = [
        "You are running inside a Telegram bridge for ChiefOfStuffVault.",
        "The final answer will be sent directly to Telegram.",
        "Use concise Czech unless the user clearly asked for another language.",
        "Use absolute dates.",
        "If you cannot complete the requested work safely in this bridge run, create a deferred task in 90_System/TaskQueue/pending/ and tell the user it was queued.",
        "Use 90_System/Skills/deferred_task_queue/task_queue.py or the canonical task template for deferred work.",
        "",
        "Always follow these local instruction files if relevant:",
        "- AGENTS.md",
        "- SOUL.md",
        "- MEMORY.md",
        "- 90_System/AgentPolicies.md",
        "- 90_System/AgentRouter.md",
        "",
        "Deferred task queue paths:",
        "- 90_System/TaskQueue/README.md",
        "- 90_System/TaskQueue/Templates/Task_TEMPLATE.md",
        "",
        "Remote request metadata:",
        f"- Local timestamp: {local_now.isoformat(timespec='seconds')}",
        f"- Local timezone: {local_now.tzname() or 'local'}",
        f"- Telegram user id: {message.get('from', {}).get('id')}",
        f"- Telegram chat id: {message.get('chat', {}).get('id')}",
        "",
        "Conversation so far:",
        _format_session_history(session),
        "",
        "Current user request:",
        user_text,
    ]
    return "\n".join(lines)


def _build_codex_command(config: BridgeConfig, output_path: Path) -> list[str]:
    launcher = _normalize_launcher_command(config.codex_command)
    return [
        *launcher,
        "-a",
        "never",
        "exec",
        "-C",
        str(config.vault_root),
        "-s",
        "workspace-write",
        "--output-last-message",
        str(output_path),
        "-",
    ]


def _normalize_launcher_command(raw_command: str) -> list[str]:
    command = raw_command.strip()
    lower = command.casefold()
    if lower.endswith(".ps1"):
        return [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            command,
        ]
    return [command]


def _acquire_lock(config: BridgeConfig) -> bool:
    lock_path = _lock_file(config)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {"started_at": _now_local().isoformat(timespec="seconds")},
                ensure_ascii=False,
            )
        )
    return True


def _release_lock(config: BridgeConfig) -> None:
    lock_path = _lock_file(config)
    if lock_path.exists():
        lock_path.unlink()


def run_codex(
    config: BridgeConfig,
    user_text: str,
    message: dict[str, Any],
    session: dict[str, Any],
) -> tuple[str, int, str]:
    prompt = _build_codex_prompt(user_text, message, session)
    temp_path = Path(
        tempfile.mkdtemp(prefix="telegram_bridge_", dir=config.runtime_dir)
    )
    try:
        output_path = temp_path / "last_message.txt"
        stdout_path = temp_path / "codex_stdout.txt"
        stderr_path = temp_path / "codex_stderr.txt"

        command = _build_codex_command(config, output_path)
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")

        started = time.monotonic()
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            capture_output=True,
            cwd=config.vault_root,
            env=env,
            timeout=config.timeout_seconds,
            encoding="utf-8",
            errors="replace",
        )
        stdout_path.write_text(completed.stdout or "", encoding="utf-8")
        stderr_path.write_text(completed.stderr or "", encoding="utf-8")
        duration = int(time.monotonic() - started)

        final_text = ""
        if output_path.exists():
            final_text = output_path.read_text(encoding="utf-8").strip()
        if not final_text:
            final_text = (completed.stdout or completed.stderr or "").strip()
        if not final_text:
            final_text = "Codex nedal zadnou odpoved."
        return final_text, completed.returncode, f"{duration}s"
    finally:
        try:
            shutil.rmtree(temp_path)
        except FileNotFoundError:
            pass
        except PermissionError as exc:
            _append_log(
                config,
                "warning",
                "Failed to clean Codex temp dir",
                temp_dir=str(temp_path),
                error=str(exc),
            )


def _handle_prompt(
    config: BridgeConfig, chat_id: int, user_text: str, message: dict[str, Any]
) -> None:
    session_key = _session_key_from_message(message)
    if session_key is None:
        send_message(config, chat_id, "Chybi identita session pro tento chat.")
        return

    if not _acquire_lock(config):
        send_message(config, chat_id, BUSY_TEXT)
        _append_log(
            config, "warning", "Rejected because bridge is busy", chat_id=chat_id
        )
        return

    started_at = _now_local().isoformat(timespec="seconds")
    session = _load_session(config, session_key)
    try:
        _append_log(
            config,
            "info",
            "Starting Codex run",
            chat_id=chat_id,
            user_id=session_key.user_id,
            prompt_preview=_safe_preview(user_text),
        )
        reply_text, exit_code, duration = run_codex(config, user_text, message, session)
        summary = f"exit={exit_code}, duration={duration}"
        _write_last_run(
            config,
            {
                "started_at": started_at,
                "ended_at": _now_local().isoformat(timespec="seconds"),
                "summary": summary,
                "prompt_preview": _safe_preview(user_text),
            },
        )
        if exit_code != 0:
            _append_session_turn(config, session_key, "user", user_text)
            reply_text = f"Codex skoncil s chybou ({summary}).\n\n{reply_text[:3000]}"
            if _context_limit_hint(reply_text):
                reply_text += "\n\nPokud je kontext uz prilis dlouhy, posli /start a zacni novou session."
        else:
            _append_session_turn(config, session_key, "user", user_text)
            _append_session_turn(config, session_key, "assistant", reply_text)
        send_message(config, chat_id, reply_text)
        _append_log(
            config,
            "info",
            "Codex run finished",
            chat_id=chat_id,
            exit_code=exit_code,
            duration=duration,
        )
    except subprocess.TimeoutExpired:
        summary = f"timeout po {config.timeout_seconds}s"
        _append_session_turn(config, session_key, "user", user_text)
        _write_last_run(
            config,
            {
                "started_at": started_at,
                "ended_at": _now_local().isoformat(timespec="seconds"),
                "summary": summary,
                "prompt_preview": _safe_preview(user_text),
            },
        )
        send_message(
            config, chat_id, f"Codex prekrocil timeout {config.timeout_seconds}s."
        )
        _append_log(
            config,
            "error",
            "Codex run timed out",
            chat_id=chat_id,
            timeout_seconds=config.timeout_seconds,
        )
    except Exception as exc:
        summary = f"bridge error: {exc}"
        _append_session_turn(config, session_key, "user", user_text)
        _write_last_run(
            config,
            {
                "started_at": started_at,
                "ended_at": _now_local().isoformat(timespec="seconds"),
                "summary": summary,
                "prompt_preview": _safe_preview(user_text),
            },
        )
        error_text = f"Bridge selhal: {exc}"
        if _context_limit_hint(error_text):
            error_text += "\n\nPokud je kontext uz prilis dlouhy, posli /start a zacni novou session."
        send_message(config, chat_id, error_text)
        _append_log(
            config,
            "error",
            "Bridge failed while handling prompt",
            chat_id=chat_id,
            error=str(exc),
        )
    finally:
        _release_lock(config)


def _is_allowed(config: BridgeConfig, message: dict[str, Any]) -> bool:
    user_id = message.get("from", {}).get("id")
    chat_id = message.get("chat", {}).get("id")
    return (
        isinstance(user_id, int)
        and isinstance(chat_id, int)
        and user_id in config.allowed_user_ids
        and chat_id in config.allowed_chat_ids
    )


def handle_update(config: BridgeConfig, update: dict[str, Any]) -> None:
    message = update.get("message")
    if not isinstance(message, dict):
        return

    user_id = message.get("from", {}).get("id")
    chat_id = message.get("chat", {}).get("id")
    if not isinstance(chat_id, int):
        return

    text, kind = _extract_text(message)
    if not _is_allowed(config, message):
        _append_log(
            config,
            "warning",
            "Rejected unauthorized message",
            user_id=user_id,
            chat_id=chat_id,
            kind=kind,
        )
        send_message(config, chat_id, "Tento chat nebo uzivatel nema pristup k bridge.")
        return

    if kind == "unsupported":
        send_message(config, chat_id, UNSUPPORTED_MESSAGE_TEXT)
        _append_log(
            config,
            "info",
            "Rejected unsupported message type",
            user_id=user_id,
            chat_id=chat_id,
        )
        return
    if text is None:
        return

    normalized = _normalize_prompt(text, config.accept_plain_text)
    if normalized is None:
        send_message(config, chat_id, "Posli /run <dotaz> nebo textovy dotaz.")
        return

    if normalized == "__START__":
        session_key = _session_key_from_message(message)
        if session_key is not None:
            _reset_session(config, session_key)
        send_message(config, chat_id, _build_start_text())
        return
    if normalized == "__HELP__":
        send_message(config, chat_id, _build_help_text())
        return
    if normalized == "__STATUS__":
        send_message(config, chat_id, _build_status_text(config))
        return

    _handle_prompt(config, chat_id, normalized, message)


def run_loop(config: BridgeConfig) -> int:
    _ensure_dirs(config)
    _append_log(config, "info", "Bridge started", vault_root=str(config.vault_root))
    offset = _load_last_update_id(config)
    while True:
        try:
            updates = get_updates(config, offset)
            for update in updates:
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = update_id + 1
                    _save_last_update_id(config, offset)
                handle_update(config, update)
        except KeyboardInterrupt:
            _append_log(config, "info", "Bridge stopped by user")
            return 0
        except Exception as exc:
            _append_log(config, "error", "Polling loop error", error=str(exc))
            time.sleep(5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Telegram -> Codex CLI bridge for ChiefOfStuffVault."
    )
    parser.add_argument("--config", help="Path to local env-style config file")
    args = parser.parse_args(argv)

    config_path = Path(args.config).resolve() if args.config else None
    config = load_config(config_path)
    return run_loop(config)


if __name__ == "__main__":
    raise SystemExit(main())
