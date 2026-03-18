---
name: "regular_day_start"
description: "Wrapper skill: run the vault morning routine across regular skills."
---

# Regular Day Start

Run the vault’s morning automations in one go. This is best-effort: each step runs even if a prior step fails, and you get a summary at the end.

## It runs
- `regular_git_submodules_pull`
- `regular_gcal_today`
- `regular_daily_brief_todoist`
- `regular_process_emails`
- `regular_web_daily_brief`

## Run
- Git submodules:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\git_submodules_pull\git_submodules_pull.ps1 -Mode remote`
- GCal meetings:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync`
- Todoist tasks:
  - `.\.venv\Scripts\python.exe 90_System\Skills\daily_brief_todoist\daily_brief_todoist.py sync`
- Process emails:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync`
- Daily News:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_sources.py fetch --pretty > 70_Exports\sources.json`
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py render --sources-file 70_Exports\sources.json --output-file 70_Exports\daily_news.md`
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py apply --content-file 70_Exports\daily_news.md`

## Notes
- Use this when the task is the routine morning prep flow.
- If aliases changed later in the day, follow up with `regular_create_links`.
