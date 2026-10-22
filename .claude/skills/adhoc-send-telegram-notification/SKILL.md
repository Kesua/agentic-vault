---
name: "adhoc-send-telegram-notification"
description: "Send one explicitly requested HTML notification to the owner's single allow-listed Telegram chat."
---

# Ad-hoc Send Telegram Notification

This is a Claude Code mirror of `adhoc_send_telegram_notification` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_send_telegram_notification/SKILL.md`
Skill class: `adhoc`

Use this skill only when the current task or routine explicitly asks for a Telegram notification. Do not send notifications merely because a routine finished.

## Required action
- If the plugin tool `send_telegram_notification` is available, call it directly and pass only the ready-to-send HTML in `html`.
- Otherwise write the HTML to `70_Exports/YYYY/MM/DD/telegram_<routine>.html` and run:
  - `.\.venv\Scripts\python.exe 90_System\Integrations\telegram_bridge\send_telegram_notification.py --html-file 70_Exports\YYYY\MM\DD\telegram_<routine>.html`
- Use dry run (`dry_run: true` or `--dry-run`) only when validation without delivery was requested or when testing the integration.

## Safety boundary
- Both paths use the existing `90_System/secrets/telegram_bridge.env` configuration (set up in the wizard's Telegram step).
- The bot token and recipient cannot be passed in; never put them in a command.
- Delivery is limited to the single chat in `TELEGRAM_ALLOWED_CHAT_IDS`; any other configuration is rejected.
- The Telegram Bridge polling process does not need to be running.
- Telegram is not end-to-end encrypted: keep summaries short and leave out amounts, credentials, health and other sensitive details.

## HTML rules
- Use only the supported basic tags `<b>`, `<i>`, `<u>`, `<s>`, `<code>`, `<pre>` and `<a href="...">`.
- Use plain newlines for line breaks; `<br>`, `<p>`, `<ul>` and `<li>` are rejected by Telegram.
- Escape dynamic `&`, `<`, and `>` characters inside text values before inserting them into HTML.
- Keep the complete rendered message at or below 4,000 characters.

## Failure handling
- A tool error means the notification was not delivered.
- If the routine itself completed, report: the routine completed, but the Telegram notification failed.
- Do not change or roll back the routine result because notification delivery failed.
