# Telegram Bridge

Local Telegram -> Codex CLI bridge for `ChiefOfStuffVault`.

## What it does
- Receives Telegram text messages through Bot API long polling.
- Validates sender against an allowlist.
- Runs `codex exec` non-interactively in the vault root.
- Returns the final Codex answer back to Telegram.
- Allows only one active Codex task at a time.
- Persists a raw per-user-per-chat session in `runtime/` from `/start` until the next `/start`.

## Files
- `telegram_bridge.py` - main runner
- Local config file: `90_System\secrets\telegram_bridge.env`
- Runtime files are written to `runtime/` and logs to `90_System/Logs/telegram_bridge/`
- Session history is stored under `runtime\sessions\`

## Run
```powershell
$env:PYTHONIOENCODING='utf-8'
.\\.venv\\Scripts\\python.exe 90_System\\Integrations\\telegram_bridge\\telegram_bridge.py --config 90_System\\secrets\\telegram_bridge.env
```

Alternative:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\run_telegram_bridge.ps1
```

Background start:
```powershell
# Run outside the sandbox.
powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\start_telegram_bridge.ps1
```

Background stop:
```powershell
# Run outside the sandbox.
powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\stop_telegram_bridge.ps1
```

## Supported Telegram commands
- `/start` - reset session history for this user+chat and begin a new thread
- `/help`
- `/status`
- `/run <prompt>`
- Plain text, if `BRIDGE_ACCEPT_PLAIN_TEXT=true`

## Limits in v1
- Text only. Voice, audio, files, and photos are rejected with guidance.
- One running job at a time.
- No public webhook endpoint; polling only.
- Full raw session history is forwarded until the next `/start`; if Codex later rejects an oversized context, reset the thread with `/start`.

## Runtime control
- Background start writes the running PID to `runtime\bridge.pid`.
- Background stop reads `runtime\bridge.pid` and removes stale PID files automatically.
- In this Codex environment, run background start/stop wrappers outside the sandbox so the bridge process persists and can be stopped reliably.
