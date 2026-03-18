---
name: "adhoc-fireflies"
description: "Wrapper skill: search Fireflies transcripts and retrieve transcript summaries/details."
---

# Ad-hoc Fireflies

This is a Claude Code mirror of `adhoc_fireflies` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_fireflies/SKILL.md`
Skill class: `adhoc`

This is a **wrapper** skill for the repo automation in `90_System/Skills/adhoc_fireflies/`.

## Scope
- Search transcripts in a date window
- Retrieve one transcript by Fireflies ID
- Read summary metadata without changing vault files

## Run (from the vault repo root)
- Search:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_fireflies\adhoc_fireflies.py search --days 30 --limit 20`
- Show one transcript:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_fireflies\adhoc_fireflies.py show --transcript-id <fireflies_id> --days 90`
- Full docs:
  - `90_System/Skills/adhoc_fireflies/SKILL.md`
