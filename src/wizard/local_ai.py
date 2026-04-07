"""Local AI setup helpers for the setup wizard."""

from __future__ import annotations

import json
import platform
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

from . import agent_cli, state

REPO_ROOT = Path(__file__).resolve().parents[2]
WINDOWS = platform.system() == "Windows"
MACOS = platform.system() == "Darwin"
LM_STUDIO_BASE_URL = "http://127.0.0.1:1234/v1"
DEFAULT_MODEL_ALIAS = "gemma-local"
DEFAULT_MODEL_LABEL = "Gemma Local"
GLOBAL_OPENCODE_CONFIG = Path.home() / ".config" / "opencode" / "opencode.json"
PROJECT_OPENCODE_CONFIG = REPO_ROOT / "opencode.json"


def _run_command(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _safe_json_loads(raw: str) -> dict | list | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _bytes_to_gb(value: int | float | None) -> float | None:
    if not value:
        return None
    return round(float(value) / (1024**3), 1)


def _windows_hardware() -> dict:
    script = """
$memory = (Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
    [pscustomobject]@{
        name = $_.Name
        vram_bytes = if ($_.AdapterRAM) { [int64]$_.AdapterRAM } else { $null }
    }
})
$wsl = $null -ne (Get-Command wsl -ErrorAction SilentlyContinue)
[pscustomobject]@{
    memory_bytes = [int64]$memory
    wsl_available = [bool]$wsl
    gpus = $gpus
} | ConvertTo-Json -Depth 4 -Compress
""".strip()
    result = _run_command(["powershell", "-NoProfile", "-Command", script], timeout=25)
    data = _safe_json_loads(result.stdout.strip()) if result.returncode == 0 else None
    if not isinstance(data, dict):
        return {
            "memory_gb": None,
            "gpus": [],
            "wsl_available": False,
            "detection_warning": "Hardware scan could not read detailed Windows GPU data.",
        }

    gpus = []
    for item in data.get("gpus", []):
        if not isinstance(item, dict):
            continue
        gpus.append(
            {
                "name": item.get("name") or "Unknown GPU",
                "vram_gb": _bytes_to_gb(item.get("vram_bytes")),
            }
        )

    return {
        "memory_gb": _bytes_to_gb(data.get("memory_bytes")),
        "gpus": gpus,
        "wsl_available": bool(data.get("wsl_available")),
        "detection_warning": None,
    }


def _macos_hardware() -> dict:
    memory_result = _run_command(["sysctl", "-n", "hw.memsize"])
    memory_bytes = None
    if memory_result.returncode == 0:
        try:
            memory_bytes = int(memory_result.stdout.strip())
        except ValueError:
            memory_bytes = None

    gpu_result = _run_command(["system_profiler", "SPDisplaysDataType", "-json"], timeout=30)
    gpu_data = _safe_json_loads(gpu_result.stdout.strip()) if gpu_result.returncode == 0 else None
    gpus = []
    if isinstance(gpu_data, dict):
        for item in gpu_data.get("SPDisplaysDataType", []):
            if not isinstance(item, dict):
                continue
            gpus.append(
                {
                    "name": item.get("sppci_model") or item.get("_name") or "Unknown GPU",
                    "vram_gb": None,
                }
            )

    return {
        "memory_gb": _bytes_to_gb(memory_bytes),
        "gpus": gpus,
        "wsl_available": False,
        "detection_warning": None if memory_bytes is not None else "Hardware scan could not read total memory on this Mac.",
    }


def detect_hardware() -> dict:
    base = {
        "os": "windows" if WINDOWS else "macos" if MACOS else platform.system().lower(),
        "arch": platform.machine().lower(),
        "cpu": platform.processor() or platform.machine(),
        "memory_gb": None,
        "gpus": [],
        "wsl_available": False,
        "detection_warning": None,
    }

    if WINDOWS:
        base.update(_windows_hardware())
    elif MACOS:
        base.update(_macos_hardware())
    else:
        base["detection_warning"] = "Local AI setup is only optimized for Windows and macOS."

    recommendation = recommend_model(base)
    base["recommendation"] = recommendation
    return base


def recommend_model(hardware: dict) -> dict:
    os_name = hardware.get("os")
    arch = hardware.get("arch", "")
    memory_gb = hardware.get("memory_gb")
    gpus = hardware.get("gpus") or []
    best_vram = max(
        [gpu.get("vram_gb") or 0 for gpu in gpus if isinstance(gpu, dict)],
        default=0,
    )

    if os_name == "windows":
        if best_vram >= 7.5:
            return {
                "tier": "proceed_e4b",
                "headline": "Recommended: proceed with Gemma 4 E4B",
                "details": "This machine looks strong enough for a practical 4-bit Gemma 4 E4B setup in LM Studio.",
                "recommended_model": "Gemma 4 E4B Instruct, 4-bit quant (Q4)",
                "can_continue": True,
                "warnings": [],
            }
        if best_vram >= 4:
            return {
                "tier": "recommend_smaller",
                "headline": "Recommended: use a smaller local model",
                "details": "Your GPU appears usable for local AI, but Gemma 4 E4B may be tight. Start with a smaller Gemma or a lighter quantized model.",
                "recommended_model": "A smaller Gemma Instruct model or a lighter quantized build",
                "can_continue": True,
                "warnings": [],
            }
        return {
            "tier": "limited_support",
            "headline": "Limited support on this machine",
            "details": "This Windows machine does not appear to have enough dedicated GPU memory for a comfortable Gemma 4 E4B setup.",
            "recommended_model": "A smaller local model",
            "can_continue": True,
            "warnings": ["LM Studio may still work, but start with a smaller model than Gemma 4 E4B."],
        }

    if os_name == "macos":
        if "arm" in arch or "apple" in arch:
            if (memory_gb or 0) >= 24:
                return {
                    "tier": "proceed_e4b",
                    "headline": "Recommended: proceed with Gemma 4 E4B",
                    "details": "This Apple Silicon Mac has enough unified memory for a realistic Gemma 4 E4B trial in LM Studio.",
                    "recommended_model": "Gemma 4 E4B Instruct, 4-bit quant",
                    "can_continue": True,
                    "warnings": [],
                }
            if (memory_gb or 0) >= 16:
                return {
                    "tier": "recommend_smaller",
                    "headline": "Recommended: use a smaller local model",
                    "details": "This Apple Silicon Mac can run local AI, but a smaller Gemma option is the safer starting point.",
                    "recommended_model": "A smaller Gemma Instruct model",
                    "can_continue": True,
                    "warnings": [],
                }
            return {
                "tier": "limited_support",
                "headline": "Limited support on this machine",
                "details": "This Apple Silicon Mac is likely below the comfortable range for Gemma 4 E4B.",
                "recommended_model": "A smaller local model",
                "can_continue": True,
                "warnings": ["Start with a smaller model to avoid poor performance or failed loads."],
            }

        return {
            "tier": "limited_support",
            "headline": "Limited support on this machine",
            "details": "Intel Macs are supported only as a guided/manual path for this setup.",
            "recommended_model": "A smaller local model",
            "can_continue": True,
            "warnings": ["Model recommendations on Intel Macs are less reliable than on Apple Silicon."],
        }

    return {
        "tier": "limited_support",
        "headline": "Limited support on this machine",
        "details": "This setup wizard currently targets Windows and macOS only.",
        "recommended_model": "A smaller local model",
        "can_continue": False,
        "warnings": ["Automatic local AI setup is not available on this platform."],
    }


def _lmstudio_request(path: str) -> tuple[bool, dict, str]:
    url = f"{LM_STUDIO_BASE_URL}{path}"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=10) as resp:
            return True, json.loads(resp.read().decode("utf-8")), ""
    except urllib.error.HTTPError as exc:
        return False, {}, f"LM Studio returned HTTP {exc.code}."
    except Exception as exc:
        return False, {}, f"Could not reach LM Studio at {LM_STUDIO_BASE_URL}: {exc}"


def lmstudio_status() -> dict:
    ok, data, error = _lmstudio_request("/models")
    if not ok:
        return {
            "ok": False,
            "reachable": False,
            "base_url": LM_STUDIO_BASE_URL,
            "models": [],
            "message": error,
        }

    models = []
    for item in data.get("data", []):
        if not isinstance(item, dict):
            continue
        model_id = item.get("id") or item.get("object") or "unknown-model"
        models.append(
            {
                "id": model_id,
                "label": item.get("id") or item.get("owned_by") or model_id,
            }
        )

    if not models:
        return {
            "ok": False,
            "reachable": True,
            "base_url": LM_STUDIO_BASE_URL,
            "models": [],
            "message": "LM Studio is reachable, but no model is loaded yet.",
        }

    return {
        "ok": True,
        "reachable": True,
        "base_url": LM_STUDIO_BASE_URL,
        "models": models,
        "message": f"LM Studio is running and reports {len(models)} loaded model(s).",
    }


def _config_path(scope: str) -> Path:
    if scope == "project":
        return PROJECT_OPENCODE_CONFIG
    return GLOBAL_OPENCODE_CONFIG


def _load_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return raw if isinstance(raw, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _looks_configured(path: Path) -> bool:
    data = _load_config(path)
    provider = data.get("provider", {})
    if not isinstance(provider, dict):
        return False
    lmstudio = provider.get("lmstudio", {})
    options = lmstudio.get("options", {}) if isinstance(lmstudio, dict) else {}
    return bool(options.get("baseURL"))


def write_opencode_config(
    scope: str,
    model_alias: str = DEFAULT_MODEL_ALIAS,
    api_key: str = "lm-studio",
    chosen_model_label: str = DEFAULT_MODEL_LABEL,
    base_url: str = LM_STUDIO_BASE_URL,
) -> dict:
    path = _config_path(scope)
    config = _load_config(path)
    provider = config.get("provider")
    if not isinstance(provider, dict):
        provider = {}
    lmstudio = provider.get("lmstudio")
    if not isinstance(lmstudio, dict):
        lmstudio = {}
    models = lmstudio.get("models")
    if not isinstance(models, dict):
        models = {}

    models[model_alias] = {
        "name": chosen_model_label or DEFAULT_MODEL_LABEL,
        "limit": {
            "context": 128000,
            "output": 8192,
        },
    }
    lmstudio.update(
        {
            "npm": "@ai-sdk/openai-compatible",
            "name": "LM Studio",
            "options": {
                "baseURL": base_url or LM_STUDIO_BASE_URL,
                "apiKey": api_key or "lm-studio",
            },
            "models": models,
        }
    )
    provider["lmstudio"] = lmstudio
    config["$schema"] = "https://opencode.ai/config.json"
    config["provider"] = provider
    config["model"] = f"lmstudio/{model_alias}"
    config["small_model"] = f"lmstudio/{model_alias}"

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    current = state.load()
    current.opencode_configured = True
    current.local_ai_selected = True
    state.save(current)
    return {
        "ok": True,
        "path": str(path),
        "scope": scope,
        "message": f"Saved OpenCode LM Studio config to {path}.",
    }


def local_ai_status() -> dict:
    current = state.load()
    opencode_status = agent_cli.detect()
    opencode = next(
        (item for item in opencode_status.get("assistants", []) if item.get("key") == "opencode"),
        None,
    )
    lmstudio = lmstudio_status()
    global_configured = _looks_configured(GLOBAL_OPENCODE_CONFIG)
    project_configured = _looks_configured(PROJECT_OPENCODE_CONFIG)

    return {
        "selected": current.local_ai_selected,
        "hardware_scanned": current.local_ai_hardware_scanned,
        "recommendation": current.local_ai_recommendation,
        "opencode": opencode,
        "opencode_configured": current.opencode_configured or global_configured or project_configured,
        "config_paths": {
            "global": str(GLOBAL_OPENCODE_CONFIG),
            "project": str(PROJECT_OPENCODE_CONFIG),
        },
        "configured_scopes": {
            "global": global_configured,
            "project": project_configured,
        },
        "lmstudio": lmstudio,
        "lmstudio_server_detected": current.lmstudio_server_detected or lmstudio.get("reachable", False),
        "lmstudio_models": current.lmstudio_models or [item["id"] for item in lmstudio.get("models", [])],
        "local_ai_completed": current.local_ai_completed,
    }


def update_hardware_state() -> dict:
    hardware = detect_hardware()
    current = state.load()
    current.local_ai_selected = True
    current.local_ai_hardware_scanned = True
    current.local_ai_recommendation = hardware["recommendation"]
    state.save(current)
    return hardware


def verify_setup() -> dict:
    status_payload = local_ai_status()
    checks = [
        {
            "label": "OpenCode installed",
            "ok": bool(status_payload.get("opencode", {}).get("installed")),
        },
        {
            "label": "OpenCode config written",
            "ok": bool(status_payload.get("opencode_configured")),
        },
        {
            "label": "LM Studio server reachable",
            "ok": bool(status_payload.get("lmstudio", {}).get("reachable")),
        },
        {
            "label": "LM Studio model loaded",
            "ok": bool(status_payload.get("lmstudio", {}).get("models")),
        },
    ]
    overall_ok = all(item["ok"] for item in checks)
    current = state.load()
    current.local_ai_selected = True
    current.lmstudio_server_detected = bool(status_payload.get("lmstudio", {}).get("reachable"))
    current.lmstudio_models = status_payload.get("lmstudio_models", [])
    current.local_ai_completed = overall_ok
    state.save(current)
    return {
        "ok": overall_ok,
        "checks": checks,
        "message": "Local AI setup is ready." if overall_ok else "Local AI setup still needs attention.",
        "status": status_payload,
    }
