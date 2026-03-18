---
name: "adhoc-clockify"
description: "Wrapper skill: read only Jan's Clockify records and explicitly create new time entries."
---

# Ad-hoc Clockify

This is a Claude Code mirror of `adhoc_clockify` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_clockify/SKILL.md`
Skill class: `adhoc`

This is a **wrapper** skill for the repo automation in `90_System/Skills/clockify_sync/`.

## Scope
- Identify the current Clockify token owner
- List projects and project tasks
- Read only the token owner's time entries in an explicit date window
- Summarize only the token owner's time by project
- Create a new time entry only on explicit request

## Useful structure
- Treat local meeting notes as the evidence source for reconstructing missing Clockify entries.
- Pick existing Clockify buckets instead of inventing labels.
- Main buckets used in this vault:
  - `FLO Data / Internal Activities`
    - Typical tasks: `Internal Meetings`, `Hiring`, `Internal Tasks`
  - `FLO Data / Sales & Presales`
    - Typical tasks: `Presale`, `Internal Sales Support Meetings`, `Client's / Partner's Meetings`
  - `FLO / Smart Scout`
    - Use for internal SmartScout coordination and internal SmartScout meetings
  - External SmartScout delivery
    - Use the relevant client project, for example `Rockaway / Smart Scout`, `Metalimex / SmartScout`, `PCI / SmartScout`
- Practical rule:
  - Internal FLO meetings go to `Internal Activities`
  - Internal SmartScout meetings go to `FLO / Smart Scout`
  - SmartScout meetings with external clients go to the relevant client-specific SmartScout project
  - Prospecting and offer-shaping meetings go to `Sales & Presales`

## Run (from the vault repo root)
- Show token owner:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py whoami`
- List entries:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py list --start "2026-03-01T00:00:00+01:00" --end "2026-03-08T00:00:00+01:00"`
- Create an entry:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py create-entry --project "Rockaway / Smart Scout" --start "2026-03-11T09:00:00+01:00" --duration-minutes 60 --description "Status sync prep"`
- Full docs:
  - `90_System/Skills/clockify_sync/SKILL.md`

## Backfill workflow
- Read the relevant meeting notes first.
- List candidate projects and tasks before creates.
- Prefer `--project-id` and `--task-id` when names are ambiguous.
