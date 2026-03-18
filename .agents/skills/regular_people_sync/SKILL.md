---
name: "regular_people_sync"
description: "Wrapper skill: create or refresh people notes from meetings and stored replied-thread participants."
---

# Regular People Sync

This is a **wrapper** skill for `90_System/Skills/meeting_attendees_people_sync/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync --dry-run`
