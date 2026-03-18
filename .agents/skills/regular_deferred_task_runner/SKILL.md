---
name: "regular_deferred_task_runner"
description: "Wrapper skill: each hour, gather pending deferred tasks into the runner todo list and process them one by one."
---

# Regular Deferred Task Runner

This is a **wrapper** skill for the repo automation in `90_System/Skills/deferred_task_queue/`.

## Use
- Start by inspecting every task currently in `pending`
- Add each pending task to your working todo list before execution
- For each task in your working todo list, first perform planning on how to complete it the most efficient way, and only then start the execution. 
- Use this as a general deferred-work runner, regardless of which system created the task

## Workflow
- List all pending tasks and turn them into explicit todo items for the current run
- Claim the oldest pending task
- Render the deterministic prompt for the claimed task
- Complete the requested work by first planning the most efficient way to do it, and then executing the plan
- Mark the task `done` with a short outcome summary, or mark it failed and retryable if it should return to `pending`
- Repeat until no pending tasks remain or the run must stop

## Run (from the vault repo root)
- List pending tasks:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py list --status pending`
- Claim the oldest pending task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py claim-next --worker desktop_codex`
- Render the runner prompt:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py render-prompt --task 90_System\TaskQueue\running\<task-file>.md`
- Complete a task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py complete --task 90_System\TaskQueue\running\<task-file>.md --summary "Finished summary"`
- Fail a task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py fail --task 90_System\TaskQueue\running\<task-file>.md --summary "Failure summary" --retryable`

## Notes
- This is a regular scheduled workflow, not an ad-hoc queue creation flow.
- Keep summaries short and operational.
- Prefer retryable failure only when the blocker is likely temporary.
- A task may originate from Telegram bridge, another automation, or a manual enqueue request; the runner should treat them uniformly.
