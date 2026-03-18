---
name: "adhoc_deferred_task_queue"
description: "Wrapper skill: create and inspect deferred tasks for follow-up work that should be picked up later."
---

# Ad-hoc Deferred Task Queue

This is a **wrapper** skill for the repo automation in `90_System/Skills/deferred_task_queue/`.

## Scope
- Create a deferred task when the current run cannot safely or practically finish work now
- Inspect the pending task queue
- Keep deferred follow-up work inside `90_System/TaskQueue/`

## Rules
- Use this only for deferred follow-up work, not for normal vault editing
- Prefer short, outcome-focused task titles
- Record the real blocker in `--blocked-by` and `--blocked-reason`
- Include the original request and the desired desktop-runner outcome
- Treat Telegram bridge failures as one valid trigger, not the only intended use case
- Use `list --status pending` to inspect what still needs pickup

## Run (from the vault repo root)
- Enqueue a task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py enqueue --title "Task title" --source deferred_follow_up --requested-by jan_papousek --blocked-by permissions --blocked-reason "The current environment could not complete the action safely" --request "Original request" --desired-outcome "What the later runner should do"`
- List pending tasks:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py list --status pending`
- Full docs:
  - `90_System/Skills/deferred_task_queue/SKILL.md`
