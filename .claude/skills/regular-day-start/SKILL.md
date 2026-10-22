---
name: "regular-day-start"
description: "Wrapper skill: run the vault morning routine across regular skills."
---

# Regular Day Start

This is a Claude Code mirror of `regular_day_start` from `.agents/skills/`.
Original source: `.agents/skills/regular_day_start/SKILL.md`
Skill class: `regular`

Run the vault’s morning automations in one go. This is best-effort: each step runs even if a prior step fails, and you get a summary at the end.

Before running, read `90_System/Memory/Routines_and_Sync.md` for known failure modes and recovery commands. Report run results in the routine output; do not append dated run logs to `MEMORY.md`.

## It runs
- `regular_git_submodules_pull`
- `regular_gcal_today`
- `regular_daily_brief_todoist`
- `regular_process_emails`
- `regular_process_slack`
- `regular_web_daily_brief`
- `regular_daily_focus` (after the syncs above; uses the stored files only)

## Run
- Git submodules:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\git_submodules_pull\git_submodules_pull.ps1 -Mode remote`
- GCal meetings:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync`
- Todoist tasks:
  - `.\.venv\Scripts\python.exe 90_System\Skills\daily_brief_todoist\daily_brief_todoist.py sync`
- Process emails:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync`
- Process Slack:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --include-dm --include-mpim`
- Daily News:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_sources.py fetch --pretty > 70_Exports\sources.json`
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py render --sources-file 70_Exports\sources.json --output-file 70_Exports\daily_news.md`
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py apply --content-file 70_Exports\daily_news.md`
- Focus topics:
  - Follow `.agents/skills/regular_daily_focus/SKILL.md`.

## Optional follow-ups (only when the routine prompt asks for them)
- **Telegram summary** — after the steps above, send today's focus topics plus a one-line count of meetings and due tasks via `adhoc_send_telegram_notification`. Title it `Day start YYYY-MM-DD`.
- **Commit** — `regular_vault_commit` with `--routine day-start`; add `--push` only if the prompt asks to push.
- Run follow-ups even if a sync step failed, and list the failed steps in the summary.

## Notes
- Use this when the task is the routine morning prep flow.
- If aliases changed later in the day, follow up with `regular_create_links`.
- The Slack step includes direct and group messages visible to the token owner in addition to channels.
- Ready-to-paste scheduled prompts: `90_System/Automations/`.
