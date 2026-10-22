---
name: "regular_fireflies_sync"
description: "Wrapper skill: sync Fireflies transcript summaries into matching meeting notes."
---

# Regular Fireflies Sync

This is a **wrapper** skill for `90_System/Skills/fireflies_sync/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --dry-run`
- Local backfill of `project`/`speakers` (no API, frontmatter only):
  - `.\.venv\Scripts\python.exe 90_System\Skills\meeting_metadata\meeting_metadata.py backfill --from YYYY-MM-DD --to YYYY-MM-DD --dry-run`

## Metadata
- Frontmatter `speakers:` = who actually spoke (transcript); `attendees:` = calendar invite. An empty `project:` is filled from `30_Projects/Journal/_project_map.json` when unambiguous.
