# Deferred Task Queue Wrappers

These are the intended wrapper definitions for environments that can write into `.agents/skills/`.

## `adhoc_deferred_task_queue`
- Purpose:
  - create a deferred task when work cannot be completed in the current run
  - inspect pending queue items
- Backing commands:
  - `task_queue.py enqueue`
  - `task_queue.py list --status pending`

## `regular_deferred_task_runner`
- Purpose:
  - scheduled desktop Codex processing of queued tasks
  - gather all `pending` tasks into the runner's working todo list before execution
  - process queued tasks one by one in oldest-first order
- Backing commands:
  - `task_queue.py list --status pending`
  - `task_queue.py claim-next --worker desktop_codex`
  - `task_queue.py render-prompt --task ...`
  - `task_queue.py complete --task ...`
  - `task_queue.py fail --task ... [--retryable]`

## Why this file exists
- The core deferred-task skill lives under `90_System/Skills/`.
- Wrapper definitions live under `.agents/skills/` when the environment can materialize them.
- Desktop Codex can later materialize these wrappers from this specification.
