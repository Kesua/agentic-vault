---
name: "adhoc_todoist"
description: "Wrapper skill: search active Todoist tasks and explicitly create new tasks with project, label, and scheduling support."
---

# Ad-hoc Todoist

This is a **wrapper** skill for the repo automation in `90_System/Skills/adhoc_todoist/`.

## Scope
- Search active tasks
- Inspect one task by ID
- Create a new Todoist task only on explicit request

## Run (from the vault repo root)
- List tasks:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py list --limit 20`
- Create a task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py create-task --content "Follow up" --project "Inbox"`
- Create a timed task with labels:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py create-task --content "Planning" --project "Admin" --label work --label planning --due-datetime "2026-03-12T10:00:00+01:00" --duration-minutes 45`
- Create a subtask in a section and assign it:
  - `.\.venv\Scripts\python.exe 90_System\Skills\adhoc_todoist\adhoc_todoist.py create-task --content "Prepare agenda" --project "Admin" --section "Meetings" --parent-id <task_id> --assignee-id <user_id>`
- Full docs:
  - `90_System/Skills/adhoc_todoist/SKILL.md`
