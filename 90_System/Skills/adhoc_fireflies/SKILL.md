---
name: "adhoc_fireflies"
description: "Ad-hoc Fireflies assistant for searching transcripts and retrieving transcript summaries/details."
---

# Ad-hoc Fireflies assistant

## What it does
- Reuses the existing Fireflies API key setup from `fireflies_sync`
- Searches transcripts in a date window
- Retrieves one transcript by Fireflies ID
- Returns transcript URL plus summary fields for agent use
- Does not write to meeting notes or other vault files

## Canonical paths
- Skill code: `90_System/Skills/adhoc_fireflies/adhoc_fireflies.py`
- Existing regular sync: `90_System/Skills/fireflies_sync/fireflies_sync.py`
- Wrapper: `.agents/skills/adhoc_fireflies/SKILL.md`

## Commands (Windows)
- Search recent transcripts:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_fireflies\adhoc_fireflies.py search --days 30 --limit 20`
- Search by text:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_fireflies\adhoc_fireflies.py search --query "budget review"`
- Show one transcript:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_fireflies\adhoc_fireflies.py show --transcript-id <fireflies_id> --days 90`

## Notes
- Read-only by default.
- v1 returns transcript metadata, URL, and summary fields.
- Full transcript text retrieval is not implemented here because the current repo integration uses stable summary fields only.
