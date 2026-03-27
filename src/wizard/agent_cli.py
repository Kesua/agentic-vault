"""Detect, install, and launch supported coding CLIs for the setup wizard."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

WINDOWS = sys.platform == "win32"
MACOS = sys.platform == "darwin"
SUPPORTED_PLATFORM = WINDOWS or MACOS

ASSISTANTS: dict[str, dict[str, str]] = {
    "codex": {
        "key": "codex",
        "label": "OpenAI Codex",
        "command": "codex",
        "package": "@openai/codex",
    },
    "claude": {
        "key": "claude",
        "label": "Claude Code",
        "command": "claude",
        "package": "@anthropic-ai/claude-code",
    },
}


def _run(
    args: list[str], timeout: int = 1800, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _append_to_path(path_value: str | None) -> None:
    if not path_value:
        return
    current = os.environ.get("PATH", "")
    parts = current.split(os.pathsep) if current else []
    if path_value not in parts:
        os.environ["PATH"] = (
            path_value + os.pathsep + current if current else path_value
        )


def _npm_prefix() -> str | None:
    npm = shutil.which("npm")
    if not npm and WINDOWS:
        npm = shutil.which("npm.cmd")
    if not npm:
        return None
    try:
        result = _run([npm, "config", "get", "prefix"], timeout=60)
    except Exception:
        return None
    prefix = (result.stdout or "").strip()
    if not prefix or prefix == "undefined":
        return None
    return prefix


def _refresh_known_paths() -> None:
    prefix = _npm_prefix()
    if prefix:
        _append_to_path(prefix if WINDOWS else str(Path(prefix) / "bin"))
    if WINDOWS:
        appdata = os.environ.get("APPDATA")
        if appdata:
            _append_to_path(str(Path(appdata) / "npm"))
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(env_name)
            if root:
                _append_to_path(str(Path(root) / "nodejs"))
    else:
        for candidate in (
            str(Path.home() / ".npm-global" / "bin"),
            "/opt/homebrew/bin",
            "/usr/local/bin",
        ):
            _append_to_path(candidate)


def _resolve_command(base_name: str) -> str | None:
    _refresh_known_paths()
    direct = shutil.which(base_name)
    if direct:
        return direct
    if WINDOWS:
        direct = shutil.which(f"{base_name}.cmd")
        if direct:
            return direct
        appdata = os.environ.get("APPDATA")
        if appdata:
            candidate = Path(appdata) / "npm" / f"{base_name}.cmd"
            if candidate.exists():
                return str(candidate)
        for env_name in ("ProgramFiles", "ProgramFiles(x86)"):
            root = os.environ.get(env_name)
            if not root:
                continue
            for candidate in (
                Path(root) / "nodejs" / f"{base_name}.cmd",
                Path(root) / "nodejs" / f"{base_name}.exe",
            ):
                if candidate.exists():
                    return str(candidate)
    else:
        for candidate in (
            Path.home() / ".npm-global" / "bin" / base_name,
            Path("/opt/homebrew/bin") / base_name,
            Path("/usr/local/bin") / base_name,
        ):
            if candidate.exists():
                return str(candidate)
    return None


def _assistant_status(key: str) -> dict[str, str | bool | None]:
    assistant = ASSISTANTS[key]
    command_path = _resolve_command(assistant["command"])
    return {
        "key": key,
        "label": assistant["label"],
        "command": assistant["command"],
        "installed": bool(command_path),
        "path": command_path,
    }


def detect() -> dict:
    assistants = [_assistant_status(key) for key in ("codex", "claude")]
    installed = [item for item in assistants if item["installed"]]
    preferred = "codex" if any(item["key"] == "codex" for item in installed) else None
    if not preferred and installed:
        preferred = installed[0]["key"]
    return {
        "supported": SUPPORTED_PLATFORM,
        "platform": "windows" if WINDOWS else "macos" if MACOS else sys.platform,
        "assistants": assistants,
        "installed_any": bool(installed),
        "preferred": preferred,
    }


def _ensure_node() -> dict[str, str | bool]:
    npm = _resolve_command("npm")
    if npm:
        return {"ok": True, "message": "npm is already available."}

    if WINDOWS:
        winget = _resolve_command("winget")
        if not winget:
            return {
                "ok": False,
                "message": "Node.js is required to install Codex, but winget is not available. Install Node.js LTS, then re-run setup.",
            }
        try:
            _run(
                [
                    winget,
                    "install",
                    "OpenJS.NodeJS.LTS",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                    "--silent",
                ],
                timeout=1800,
            )
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Failed to install Node.js via winget: {exc}",
            }
    elif MACOS:
        brew = _resolve_command("brew")
        if not brew:
            return {
                "ok": False,
                "message": "Node.js is required to install Codex, but Homebrew is not available. Install Homebrew or Node.js, then re-run setup.",
            }
        try:
            _run([brew, "install", "node"], timeout=1800)
        except Exception as exc:
            return {
                "ok": False,
                "message": f"Failed to install Node.js via Homebrew: {exc}",
            }
    else:
        return {
            "ok": False,
            "message": "Automatic assistant installation is only supported on Windows and macOS.",
        }

    npm = _resolve_command("npm")
    if not npm:
        return {
            "ok": False,
            "message": "Node.js installation finished, but npm is still not on PATH. Open a new terminal and re-run setup.",
        }
    return {"ok": True, "message": "Installed Node.js."}


def install_default() -> dict:
    status = detect()
    if not status["supported"]:
        return {
            "ok": False,
            "message": "Automatic assistant installation is only supported on Windows and macOS.",
        }
    if status["installed_any"]:
        return {
            "ok": True,
            "message": "A supported coding assistant is already installed.",
            "status": status,
        }

    node_result = _ensure_node()
    if not node_result["ok"]:
        return {"ok": False, "message": node_result["message"], "status": detect()}

    npm = _resolve_command("npm")
    if not npm:
        return {
            "ok": False,
            "message": "npm is still unavailable after installing Node.js.",
            "status": detect(),
        }

    target = ASSISTANTS["codex"]
    try:
        _run([npm, "install", "-g", target["package"]], timeout=1800)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        return {
            "ok": False,
            "message": f"Failed to install {target['label']}: {detail}",
            "status": detect(),
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Failed to install {target['label']}: {exc}",
            "status": detect(),
        }

    status = detect()
    installed = next(
        (item for item in status["assistants"] if item["key"] == "codex"), None
    )
    if installed and installed["installed"]:
        return {
            "ok": True,
            "message": "Installed OpenAI Codex for this machine.",
            "installed": installed,
            "status": status,
        }
    return {
        "ok": False,
        "message": "Codex installation finished, but the command is still not available. Open a new terminal and re-run setup.",
        "status": status,
    }


def launch(key: str) -> dict:
    if key not in ASSISTANTS:
        return {"ok": False, "message": f"Unknown assistant: {key}"}
    status = detect()
    assistant = next(
        (item for item in status["assistants"] if item["key"] == key), None
    )
    if not assistant or not assistant["installed"]:
        return {"ok": False, "message": f"{ASSISTANTS[key]['label']} is not installed."}

    command = assistant["path"] or ASSISTANTS[key]["command"]
    try:
        if WINDOWS:
            subprocess.Popen(
                [
                    "powershell",
                    "-NoExit",
                    "-Command",
                    f"Set-Location -LiteralPath '{REPO_ROOT}'; & '{command}'",
                ],
                cwd=REPO_ROOT,
            )
        elif MACOS:
            safe_repo = str(REPO_ROOT).replace("\\", "\\\\").replace('"', '\\"')
            safe_cmd = str(command).replace("\\", "\\\\").replace('"', '\\"')
            apple_script = (
                'tell application "Terminal"\n'
                "activate\n"
                f'do script "cd \\"{safe_repo}\\" && \\"{safe_cmd}\\""\n'
                "end tell\n"
            )
            subprocess.Popen(["osascript", "-e", apple_script], cwd=REPO_ROOT)
        else:
            return {
                "ok": False,
                "message": "Launching a coding assistant is only supported on Windows and macOS.",
            }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Failed to launch {ASSISTANTS[key]['label']}: {exc}",
        }

    return {
        "ok": True,
        "message": f"Started {ASSISTANTS[key]['label']} in the vault folder.",
    }
