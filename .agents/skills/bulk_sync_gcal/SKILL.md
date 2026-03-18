---
name: "bulk_sync_gcal"
description: "Wrapper skill: sync Google Calendar meetings for a caller-provided day window into meeting notes."
---

# Bulk Sync GCal

This is a **wrapper** skill for `90_System/Skills/gcal_today/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync --days-back 30`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync --days-back 30 --dry-run`

## Notes
- Replace `30` with the requested day window.
- This uses the same deterministic sync as `regular_gcal_today`, but with a custom window.
