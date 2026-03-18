---
name: "bulk-sync-gmail"
description: "Wrapper skill: backfill Gmail mailbox summaries and replied-thread snapshots for a caller-provided day window."
---

# Bulk Sync Gmail

This is a Claude Code mirror of `bulk_sync_gmail` from `.agents/skills/`.
Original source: `.agents/skills/bulk_sync_gmail/SKILL.md`
Skill class: `bulk`

This is a **wrapper** skill for `90_System/Skills/process_emails/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync --days-back 30`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync --days-back 30 --dry-run`

## Notes
- Replace `30` with the requested day window.
- This backfills both daily email summaries and latest replied-thread snapshots.
