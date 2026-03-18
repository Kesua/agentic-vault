---
name: "regular-create-links"
description: "Wrapper skill: run the deterministic alias-to-wikilink pass."
---

# Regular Create Links

This is a Claude Code mirror of `regular_create_links` from `.agents/skills/`.
Original source: `.agents/skills/regular_create_links/SKILL.md`
Skill class: `regular`

This is a **wrapper** skill for `90_System/Skills/create_links/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\create_links\create_links.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\create_links\create_links.py sync --dry-run`
