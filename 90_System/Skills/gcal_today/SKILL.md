---
name: "regular_gcal_today"
description: "Regular Google Calendar sync: update upcoming meeting notes (today + 14 days, two accounts) and refresh the meeting index."
---

# Google Calendar → meeting notes

## What it does
- Authenticates to Google Calendar for `private` and `personal` accounts (OAuth)
- Fetches *timed* events from each account’s `primary` calendar for **today + the next 14 days** in the regular flow
- Supports historical backfill for the **last N days up to today** via `--days-back N`
- Filters to events that have at least one attendee email (skips events with no attendees)
- Creates/updates one note per event in `20_Meetings/YYYY/MM/DD/` named `HHmm - Title.md`
- Populates the note from `20_Meetings/Templates/MeetingNote_TEMPLATE.md`
- Preserves your manual content starting at the `## Preparation` heading (if it already exists in the note)
- Adds missing links into `20_Meetings/_MeetingIndex.md` under the relevant month section(s)
- If the same event exists in both accounts, only one note is kept (private wins)

## Canonical path + ownership
- Meeting note path: `20_Meetings/YYYY/MM/DD/HHmm - Title.md`
- Template: `20_Meetings/Templates/MeetingNote_TEMPLATE.md`
- This skill owns meeting note creation/update from calendar data and keeps `20_Meetings/_MeetingIndex.md` in sync.

## Extra metadata (for Fireflies pairing)
- Adds `- GCal cal_id: ...` into the note’s `## Calendar (auto)` section (derived from `iCalUID` + the event’s start in UTC).


## Commands (Windows)
Run these from the repository root (the folder that contains `90_System/`).

- Sync upcoming meetings (today + 14 days):
  - `.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync`
- Dry run (prints what it would change, no writes):
  - `.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync --dry-run`
- Extended window / bulk backfill:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync --days-back 30`

How to renew expired tokens it:
  - Run:

  .\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py auth --account personal

  - If private ever fails the same way, run:

  .\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py auth --account private

## Troubleshooting
- `Unable to create process using ...WindowsApps...python.exe`: you’re likely using the Microsoft Store Python / App Execution Aliases.
- Fix (recommended):
  - Install Python from python.org (not the Microsoft Store) and ensure it’s on PATH.
  - Verify `where.exe python` returns something like `...\AppData\Local\Programs\Python\Python3xx\python.exe` (and not `...\WindowsApps\python.exe`).
  - Recreate the venv (pick one):
    - Safer (keep the old one): create a new venv folder and adjust commands accordingly (e.g. `.venv2`).
    - Standard: delete and recreate `.venv`:
      - `Remove-Item -Recurse -Force .\.venv`
      - `python -m venv .venv`
  - Reinstall deps:
    - `.\.venv\Scripts\pip.exe install -r requirements.txt`
- If you see changes in `.obsidian/workspace.json`, it’s usually Obsidian state (last opened files), not the sync itself; revert if you want a clean git diff.

## Files used
- Template: `20_Meetings/Templates/MeetingNote_TEMPLATE.md`
- Index: `20_Meetings/_MeetingIndex.md`
- Wrapper: `.agents/skills/regular_gcal_today/SKILL.md`
- Bulk wrapper: `.agents/skills/bulk_sync_gcal/SKILL.md`
