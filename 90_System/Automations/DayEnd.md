# Day end — scheduled prompt

Suggested schedule: every day at 16:00.

```text
Run the regular_day_end skill from this vault, including the regular_missed_replies step.

Optional — keep the lines you want:
- Send me a Telegram reminder with the "Possibly forgotten" list via adhoc_send_telegram_notification.
- Commit the results with regular_vault_commit (--routine day-end).
- Push the commit (add --push).

Finish with a short report: which steps succeeded, which failed and why, and what I need to do (for example re-authorize an account).
```
