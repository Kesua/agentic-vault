# Telegram Bridge Setup

## Purpose
- Set up a local Telegram bot that forwards text prompts to Codex CLI running in this vault.

## 1. Create the Telegram bot
- Open Telegram and start a chat with `@BotFather`.
- Send `/newbot`.
- Enter a display name for the bot.
- Enter a unique username ending with `bot`, for example `jan_codex_bridge_bot`.
- BotFather returns a bot token like `123456789:ABC...`.
- Store that token in a local untracked file, not in git.

## 2. Prepare local configuration
- Create or move your local bridge config file to `90_System\secrets\telegram_bridge.env`.
- Fill at least:
  - `TELEGRAM_BOT_TOKEN`
  - `TELEGRAM_ALLOWED_USER_IDS`
  - `TELEGRAM_ALLOWED_CHAT_IDS`
- Keep `VAULT_ROOT` as `C:\Users\jan.papousek\ChiefOfStuffVault` unless you intentionally run against another repo.

## 3. Get your Telegram IDs
- Start a chat with your new bot and send `/start`.
- Run the bridge once with the config file.
- The bridge logs rejected or accepted message metadata including `user_id` and `chat_id`.
- Copy those IDs into `TELEGRAM_ALLOWED_USER_IDS` and `TELEGRAM_ALLOWED_CHAT_IDS`.

## 4. Run the bridge
```powershell
$env:PYTHONIOENCODING='utf-8'
.\\.venv\\Scripts\\python.exe 90_System\\Integrations\\telegram_bridge\\telegram_bridge.py --config 90_System\\secrets\\telegram_bridge.env
```

Or use the wrapper:
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\run_telegram_bridge.ps1
```

Background control:
```powershell
# Run both commands outside the sandbox in Codex.
powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\start_telegram_bridge.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\stop_telegram_bridge.ps1
```

## 5. Test end to end
- Send `/help`.
- Send `/status`.
- Send `/run summarize what changed in my vault today`.
- Verify that the reply comes back and logs appear under `90_System\Logs\telegram_bridge\`.
- Use `/start` to begin a fresh remembered thread for that user+chat. The bridge keeps raw queries and replies in runtime session files until the next `/start`.

## Telegram API note
- For this bot workflow you do not need Telegram user API credentials.
- You only need the Bot API token from `@BotFather`.
- The bridge uses standard Bot API HTTPS calls such as `getUpdates` and `sendMessage`.

## Security notes
- Only allow your own `user_id` and trusted `chat_id`.
- Do not expose the bot token in notes, screenshots, commits, or Telegram replies.
- This bridge is text-only in v1. Voice messages are rejected on purpose.

## Troubleshooting
- If background start says it worked but the bridge is gone moments later:
  - rerun start outside the sandbox
  - inspect the latest bridge log
- If `/start` never arrives:
  - verify the token
  - verify the bot chat was opened manually once
  - verify outbound HTTPS from the PC
- If Codex hangs:
  - verify `codex exec` works locally
  - reduce prompt complexity
  - inspect the latest bridge log
- If the bridge rejects your message:
  - copy the logged `user_id` and `chat_id` into the local env file
