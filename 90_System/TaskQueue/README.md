# Deferred Task Queue

Purpose
- Capture work that the Telegram bridge cannot safely or technically finish in the current run.
- Keep a durable, auditable queue inside the vault so desktop Codex can process it later.

## Folder layout
- `90_System/TaskQueue/pending/`
  - New deferred tasks waiting for pickup.
- `90_System/TaskQueue/running/`
  - Claimed by a worker and currently being processed.
- `90_System/TaskQueue/done/`
  - Finished tasks kept for audit.
- `90_System/TaskQueue/failed/`
  - Exhausted or manually failed tasks.
- `90_System/TaskQueue/Templates/Task_TEMPLATE.md`
  - Canonical task file structure.

## State model
- `pending`
  - Fresh task, no worker currently owns it.
- `running`
  - Claimed by one worker.
- `done`
  - Successfully completed.
- `failed`
  - Failed and not automatically retried.

## Canonical rule for Telegram bridge
- If the bridge-side Codex cannot complete a request because of permissions, sandbox, missing capability, or because the work should be done later on desktop Codex, it should:
  - create a task in `pending/`
  - explain in Telegram that the work was queued
  - include the task id or path in the reply

## Task content
- Use one file per task.
- Keep YAML frontmatter structured for automation.
- Keep human-readable sections below for direct Obsidian review.

## Queue helper
- Main helper:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py`

Useful commands
- Enqueue:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py enqueue --title "Update bridge skills outside vault" --source telegram_bridge --requested-by telegram_user_8768437485 --blocked-by permissions --request "Update the skill files used by the desktop Codex instance." --desired-outcome "Desktop Codex updates the external skill files and verifies them." --constraint "Do not edit outside approved paths from Telegram bridge."`
- List pending:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py list --status pending`
- Claim next pending task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py claim-next --worker desktop_codex`
- Render a desktop-runner prompt for a claimed task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py render-prompt --task 90_System\TaskQueue\running\<task-file>.md`
- Complete a task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py complete --task 90_System\TaskQueue\running\<task-file>.md --summary "Implemented and verified."`
- Fail a task:
  - `.\.venv\Scripts\python.exe 90_System\Skills\deferred_task_queue\task_queue.py fail --task 90_System\TaskQueue\running\<task-file>.md --summary "Blocked by missing OAuth token." --retryable`

## Recommended hourly desktop automation
1. Run `claim-next --worker desktop_codex`.
2. If no task exists, stop.
3. Run `render-prompt` for the claimed task.
4. Start desktop Codex with that prompt.
5. If the task is finished, run `complete`.
6. If it failed but should be retried later, run `fail --retryable`.
7. If it failed permanently, run `fail`.

## Operational guidance
- Keep `max_attempts` low, typically `3`.
- Prefer `done/` retention over immediate deletion.
- Run cleanup separately if audit history gets too large.
- Do not let the runner process files outside this queue without an explicit prompt.
