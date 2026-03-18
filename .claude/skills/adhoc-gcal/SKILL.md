---
name: "adhoc-gcal"
description: "Wrapper skill: inspect Google Calendar meetings and create draft-confirmed events."
---

# Ad-hoc Google Calendar

This is a Claude Code mirror of `adhoc_gcal` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_gcal/SKILL.md`
Skill class: `adhoc`

This is a **wrapper** skill for the repo automation in `90_System/Skills/adhoc_gcal/`.

## Scope
- List/search upcoming meetings
- Inspect one event
- Create local meeting drafts and confirm them into real calendar events

## Run (from the vault repo root)
- Authenticate:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py auth --account private`
- List meetings:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py list --account both --days 14`
- Create a draft:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_gcal\adhoc_gcal.py create-meeting-draft --account private --title "Planning" --start "2026-03-12T10:00:00+01:00"`
- Full docs:
  - `90_System/Skills/adhoc_gcal/SKILL.md`
