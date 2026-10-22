---
name: "regular_day_end"
description: "Wrapper skill: run the vault end-of-day routine across regular skills."
---

# Regular Day End

Run the vault’s end-of-day automations in order so transcripts, mailbox exports, people notes, and links stay in sync.

## It runs
- `regular_fireflies_sync`
- `regular_process_emails`
- `regular_process_slack`
- `regular_people_sync`
- `regular_create_links`
- `regular_missed_replies` (after the syncs above; uses the stored files only)

## Run
- Fireflies sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync`
- Process emails:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync`
- Process Slack:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --include-dm --include-mpim`
- People sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync`
- Create links:
  - `.\.venv\Scripts\python.exe 90_System\Skills\create_links\create_links.py sync`
- Missed replies:
  - Follow `.agents/skills/regular_missed_replies/SKILL.md`.

## Optional follow-ups (only when the routine prompt asks for them)
- **Telegram reminder** — after the steps above, send the "Possibly forgotten" list via `adhoc_send_telegram_notification`. Title it `Before you log off — YYYY-MM-DD`; with no findings, send one short line.
- **Commit** — `regular_vault_commit` with `--routine day-end`; add `--push` only if the prompt asks to push.
- Run follow-ups even if a sync step failed, and list the failed steps in the summary.

## Notes
- Use this when the task is the routine end-of-day sync flow.
- This is a regular deterministic workflow, not an exploratory one.
- The Slack step includes direct and group messages visible to the token owner in addition to channels.
- Ready-to-paste scheduled prompts: `90_System/Automations/`.
