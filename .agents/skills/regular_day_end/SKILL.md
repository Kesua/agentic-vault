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

## Run
- Fireflies sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync`
- Process emails:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync`
- Process Slack:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync`
- People sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync`
- Create links:
  - `.\.venv\Scripts\python.exe 90_System\Skills\create_links\create_links.py sync`

## Notes
- Use this when the task is the routine end-of-day sync flow.
- This is a regular deterministic workflow, not an exploratory one.
