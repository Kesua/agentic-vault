---
name: "adhoc-clockify"
description: "Wrapper skill: read only the current Clockify token owner's records and explicitly create new time entries."
---

# Ad-hoc Clockify

This is a Claude Code mirror of `adhoc_clockify` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_clockify/SKILL.md`
Skill class: `adhoc`

This wraps `90_System/Skills/clockify_sync/adhoc_clockify.py`.

## Scope
- Identify the current Clockify token owner.
- List projects and project tasks in the connected workspace.
- Read and summarize only the token owner's time entries in an explicit date window.
- Create a new time entry only on explicit request.

## Rules
- Use local notes as evidence when reconstructing time entries.
- Choose existing Clockify projects and tasks; do not invent labels.
- List candidates before creating entries, and use IDs when names are ambiguous.
- Follow `90_System/Skills/clockify_sync/SKILL.md` for commands and guardrails.
