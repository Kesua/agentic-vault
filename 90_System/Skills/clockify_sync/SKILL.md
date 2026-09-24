---
name: "clockify_sync"
description: "Clockify assistant for reading the current token owner's records and explicitly creating new time entries."
---

# Clockify assistant

## What it does
- Uses the local Clockify API token from `90_System/secrets/clockify_token.txt`.
- Reads only the current token owner's records.
- Lists active projects and project tasks in the active workspace.
- Lists and summarizes time entries in an explicit date window.
- Creates a new time entry only when explicitly requested.

## Guardrails
- No command accepts a user ID override.
- All reads and creates are scoped to the token owner returned by `GET /api/v1/user`.
- Use this skill for Clockify access; do not make direct API calls from the agent.
- Choose an existing project and task from the connected workspace. Resolve ambiguous names with `--project-id` and `--task-id`.

## Commands (Windows)
- Show the token owner: `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py whoami`
- List projects: `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py projects`
- List tasks: `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py tasks --project "Project name"`
- List entries: `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py list --start "2026-03-01T00:00:00+01:00" --end "2026-03-08T00:00:00+01:00"`
- Create an entry: `.\.venv\Scripts\python.exe 90_System\Skills\clockify_sync\adhoc_clockify.py create-entry --project "Project name" --start "2026-03-11T09:00:00+01:00" --duration-minutes 60 --description "Work completed"`

Use ISO datetimes with timezone offsets. If `--end` is omitted on `create-entry`, pass `--duration-minutes`.
