---
name: "adhoc_gcal"
description: "Ad-hoc Google Calendar assistant for inspecting meetings and creating draft-confirmed events."
---

# Ad-hoc Google Calendar assistant

## What it does
- Uses the existing Google Calendar OAuth client files
- Stores separate ad-hoc tokens with event write scope
- Lists/searches upcoming meetings
- Shows one event by Google Calendar event ID
- Creates local draft notes for proposed new meetings
- Creates the actual event only when you explicitly confirm a draft

## Canonical paths
- Skill code: `90_System/Skills/adhoc_gcal/adhoc_gcal.py`
- Draft notes: `70_Exports/gcal_drafts/`
- Existing regular sync: `90_System/Skills/gcal_today/gcal_today.py`
- Wrapper: `.agents/skills/adhoc_gcal/SKILL.md`

## Commands (Windows)
- Authenticate:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py auth --account private`
- List meetings:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py list --account both --days 14`
- Show one event:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py show --account both --event-id <event_id>`
- Create a draft:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py create-meeting-draft --account private --title "Planning" --start "2026-03-12T10:00:00+01:00" --duration-minutes 45 --attendee name@example.com`
- Confirm a draft:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py confirm-draft-create --draft 70_Exports\gcal_drafts\<draft_file>.md`

## Notes
- Read operations are safe defaults.
- Google Calendar has no native draft object in this workflow; the local markdown draft is the confirmation surface.
- v1 creates standard events only and does not auto-generate Meet links.
