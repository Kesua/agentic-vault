---
name: "bulk-sync-fireflies"
description: "Wrapper skill: backfill Fireflies transcript summaries into matching meeting notes for a caller-provided day window."
---

# Bulk Sync Fireflies

This is a Claude Code mirror of `bulk_sync_fireflies` from `.agents/skills/`.
Original source: `.agents/skills/bulk_sync_fireflies/SKILL.md`
Skill class: `bulk`

This is a **wrapper** skill for `90_System/Skills/fireflies_sync/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --days-back 30`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --days-back 30 --dry-run`

## Notes
- Replace `30` with the requested day window.
- This uses the same deterministic sync as `regular_fireflies_sync`, but with a custom historical window.
