---
name: "regular-fireflies-sync"
description: "Wrapper skill: sync Fireflies transcript summaries into matching meeting notes."
---

# Regular Fireflies Sync

This is a Claude Code mirror of `regular_fireflies_sync` from `.agents/skills/`.
Original source: `.agents/skills/regular_fireflies_sync/SKILL.md`
Skill class: `regular`

This is a **wrapper** skill for `90_System/Skills/fireflies_sync/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --dry-run`
