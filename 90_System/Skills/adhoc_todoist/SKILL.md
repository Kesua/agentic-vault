---
name: "adhoc_todoist"
description: "Ad-hoc Todoist assistant for searching active tasks and explicitly creating new tasks with project, label, and scheduling support."
---

# Ad-hoc Todoist assistant

## What it does
- Reads the existing Todoist API token from `90_System/secrets/todoist_token_personal.json`
- Lists active tasks with local filtering for query, project, label, due date, and priority
- Shows one Todoist task by ID
- Creates a new Todoist task only when you explicitly call `create-task` or `create-inbox-task`
- Supports custom project, section, labels, assignee, due date, due datetime, duration for timed tasks, and parent task IDs for subtasks
- Does not update, complete, or delete tasks in v1
- Does not write to the vault in v1

## Canonical paths
- Skill code: `90_System/Skills/adhoc_todoist/adhoc_todoist.py`
- Existing regular sync: `90_System/Skills/daily_brief_todoist/daily_brief_todoist.py`
- Wrapper: `.agents/skills/adhoc_todoist/SKILL.md`

## Commands (Windows)
- List tasks:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py list --limit 20`
- Search tasks:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py list --query "invoice" --project "Admin"`
- Show one task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py show --task-id <task_id>`
- Create a task in a chosen project:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py create-task --content "Follow up with vendor" --project "Admin" --label waiting --due-datetime "2026-03-12T09:00:00+01:00" --duration-minutes 30`
- Create a subtask in a section and assign it:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py create-task --content "Prepare agenda" --project "Admin" --section "Meetings" --parent-id <task_id> --assignee-id <user_id> --label planning --due-datetime "2026-03-12T10:00:00+01:00" --duration-minutes 45`
- Create an Inbox task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py create-inbox-task --content "Follow up with vendor" --due-string "tomorrow 9am"`

## Notes
- Read operations are the default.
- `create-task` is the general write command.
- `create-inbox-task` remains as a compatibility alias that defaults to Inbox when no project is provided.
- For multiple labels, repeat `--label`.
- `--duration-minutes` is intended for timed tasks and requires `--due-datetime`.
- `--section` resolves by section name and is safest when paired with a project.
- `--parent-id` creates a subtask under an existing Todoist task.
- `--assignee-id` passes a Todoist assignee user ID for shared tasks.
- Project name matching can be ambiguous; use `--project-id` when needed.
