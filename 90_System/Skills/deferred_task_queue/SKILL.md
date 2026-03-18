---
name: "deferred_task_queue"
description: "Manage deferred tasks for work that should be picked up later by a scheduled or manual runner."
---

# Deferred Task Queue

## What it does
- Writes deferred work requests into `90_System/TaskQueue/pending/`
- Lets a desktop worker claim one task at a time
- Moves tasks across `pending`, `running`, `done`, and `failed`
- Renders a deterministic desktop-runner prompt from the stored task record
- Supports multiple enqueue sources, including Telegram bridge failures when they occur

## Commands (Windows)
- Enqueue:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py enqueue --title "Task title" --source deferred_follow_up --requested-by jan_papousek --blocked-by permissions --request "Original request" --desired-outcome "What the later runner should do"`
- List pending:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py list --status pending`
- Claim oldest pending task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py claim-next --worker desktop_codex`
- Render runner prompt:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py render-prompt --task 90_System\TaskQueue\running\<task-file>.md`
- Complete:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py complete --task 90_System\TaskQueue\running\<task-file>.md --summary "Finished summary"`
- Fail:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py fail --task 90_System\TaskQueue\running\<task-file>.md --summary "Failure summary" --retryable`

## Notes
- Use this when work should be deferred to a later manual or scheduled run.
- Telegram bridge failures are one valid trigger for queueing work, not the defining purpose of the queue.
- Keep task titles short and outcome-focused.
- Prefer `render-prompt` for deterministic desktop automation.
