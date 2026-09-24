# Agent Router

- Purpose: deterministic guidance for Telegram-triggered Codex runs.
- Scope: Vault operations initiated by the local Telegram bridge.

## Supported intents

### Daily brief for today
- Examples:
  - `daily brief today`
  - `tell me my daily brief for today`
  - `refresh brief for today`
- Recommended actions:
  - Run Todoist sync if task freshness matters.
  - Run Google Calendar sync if meeting freshness matters.
  - Refresh web daily brief only when the user asks for news refresh or current news.
  - Read today's Daily Brief note and summarize it for Telegram.
- Reply:
  - Include the absolute date in the user's local timezone.
  - Summarize key tasks, meetings, and news in short bullets.

### Daily brief for a specific date
- Examples:
  - `daily brief 2026-03-11`
  - `show daily brief for 2026-03-11`
- Recommended actions:
  - Read the matching Daily Brief note if it exists.
  - Do not refresh external sources unless the user explicitly asks for refresh.

### Meetings today
- Examples:
  - `meetings today`
  - `what meetings do I have today`
- Recommended actions:
  - Run calendar sync if needed.
  - Read today's meeting notes or calendar-derived notes and summarize.

### Search or read vault content
- Examples:
  - `find note about invoicing`
  - `search the vault for ...`
  - `read note ...`
- Recommended actions:
  - Prefer read-only search commands and existing files.
  - Return a concise answer with file references when useful.

## Behavioral routing
- If the user asks for unsupported media handling like voice transcription, explain that this bridge version supports text only.
- For risky or ambiguous remote write requests, apply the strict repo instructions and avoid destructive actions.
- For routine vault tasks, prefer existing skills under `90_System\Skills\`.
- For work blocked by bridge permissions, unsupported capabilities, or actions that should run later on desktop Codex:
  - create a deferred task in `90_System/TaskQueue/pending/`
  - use `90_System/Skills/deferred_task_queue/task_queue.py`
  - tell the user the task was queued and include its id/path
