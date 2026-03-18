---
name: "regular_people_sync"
description: "Regular people sync: create or update people notes from meetings and stored replied-thread participants."
---

# People sync

## What it does
- Scans `20_Meetings/YYYY/MM/DD/*.md` for frontmatter `attendees:`
- Scans `00_Mailbox/YYYY/MM/DD/*.md` for stored email-thread `participants:`
- Matches attendees to existing people notes in `40_People/` by email first, then aliases
- Creates missing person notes from `40_People/Templates/person_TEMPLATE.md`
- Updates existing person notes with newly seen attendee emails/aliases and latest `last_touch`
- Ensures person notes contain both `## Meetings` and `## Emails` query sections
- Refreshes `40_People/_PeopleIndex.md` with an auto-managed contacts section

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync --dry-run`
- Refresh layout only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py refresh-layout`

## Notes
- This sync only manages people-note existence and basic identity fields.
- It does not try to infer org, role, team, or timezone.
- After this step, run `regular_create_links` so the new aliases become wikilinks across the vault.
