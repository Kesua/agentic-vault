---
name: "adhoc_send_telegram_notification"
description: "Send one explicitly requested HTML notification through the allow-listed Telegram notifier plugin."
---

# Ad-hoc Send Telegram Notification

Use this skill only when the current task or routine explicitly asks for a Telegram notification. Do not send notifications merely because a routine finished.

## Required action
- Call the plugin tool `send_telegram_notification` directly.
- Pass only the ready-to-send HTML in `html`.
- Use `dry_run: true` only when validation without delivery was requested or when testing the integration.
- Never invoke the underlying Python helper through a shell when this plugin tool is available.

## Safety boundary
- The tool always uses the existing `90_System/secrets/telegram_bridge.env` configuration.
- The bot token and recipient cannot be passed to the tool.
- Delivery is limited to the single chat in `TELEGRAM_ALLOWED_CHAT_IDS`; any other configuration is rejected.
- The Telegram Bridge polling process does not need to be running.

## HTML rules
- Prefer the supported basic tags `<b>`, `<i>`, `<code>`, `<pre>`, and `<a>`.
- Escape dynamic `&`, `<`, and `>` characters inside text values before inserting them into HTML.
- Keep the complete rendered message at or below 4,000 characters.
- Never pass a bot token or chat id in the command.

## Failure handling
- A tool error means the notification was not delivered.
- If the routine itself completed, report: the routine completed, but the Telegram notification failed.
- Do not change or roll back the routine result because notification delivery failed.
