---
name: "clockify_sync"
description: "Ad-hoc Clockify assistant for reading only Jan's records and explicitly creating new time entries through the repo token."
---

# Ad-hoc Clockify assistant

## What it does
- Uses the existing Clockify API token from `90_System/secrets/clockify_token.txt`
- Reads only the current token owner's records
- Lists active projects and project tasks in the active workspace
- Lists time entries in an explicit date window
- Summarizes time by project in an explicit date window
- Creates a new time entry only when explicitly requested

## Structure used in this vault
- Reporting depends primarily on the correct project and task, not on the description text.
- Main bucket types:
  - Internal FLO work
    - Project: `FLO Data / Internal Activities`
    - Typical tasks: `Internal Meetings`, `Hiring`, `Internal Tasks`
  - FLO presales / internal business development
    - Project: `FLO Data / Sales & Presales`
    - Typical tasks: `Presale`, `Internal Sales Support Meetings`, `Client's / Partner's Meetings`
  - SmartScout work
    - Internal SmartScout coordination:
      - Project: `FLO / Smart Scout`
    - External client delivery:
      - Use the client-specific SmartScout project, for example `Rockaway / Smart Scout`, `Metalimex / SmartScout`, or `PCI / SmartScout`
- Practical rule:
  - Internal FLO meetings go to `Internal Activities`
  - Internal SmartScout meetings go to `FLO / Smart Scout`
  - SmartScout meetings with external attendees go to the relevant client-specific SmartScout project
  - Prospecting and offer-shaping meetings go to `Sales & Presales`

## Guardrails
- No command accepts a user ID override
- All reads and creates are scoped to the token owner returned by `GET /api/v1/user`
- This skill must be used instead of ad-hoc direct Clockify API calls from the agent

## Canonical paths
- Skill code: `90_System/Skills/clockify_sync/adhoc_clockify.py`
- Token file: `90_System/secrets/clockify_token.txt`
- Wrapper: `.agents/skills/adhoc_clockify/SKILL.md`
- Current token owner ID noted in script description: `6777eb65c22bea50e6e1c8f9`

## Commands (Windows)
- Show the token owner:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py whoami`
- List projects:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py projects --query "Rockaway"`
- List tasks for one project:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py tasks --project "Rockaway / Smart Scout"`
- List entries in a window:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py list --start "2026-03-01T00:00:00+01:00" --end "2026-03-08T00:00:00+01:00"`
- Summarize time in a window:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py summary --start "2026-01-01T00:00:00+01:00" --end "2026-02-01T00:00:00+01:00"`
- Create one entry:
  - `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py create-entry --project "Rockaway / Smart Scout" --start "2026-03-11T09:00:00+01:00" --duration-minutes 90 --description "Prep for roadmap review"`

## Notes
- Use ISO datetimes with timezone offsets when possible.
- If `--end` is omitted on `create-entry`, the command uses `--duration-minutes`.
- Project and task name matching is intentionally strict: ambiguous matches fail fast.
- In this workspace, SmartScout project names are ambiguous across clients. For backfills, resolve projects first and prefer `--project-id` and `--task-id` when creating entries.
