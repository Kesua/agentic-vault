---
name: "regular-process-slack"
description: "Wrapper skill: export Slack summaries and thread snapshots into `00_Mailbox/` from approved conversations."
---

# Regular Process Slack

This is a Claude Code mirror of `regular_process_slack` from `.agents/skills/`.
Original source: `.agents/skills/regular_process_slack/SKILL.md`
Skill class: `regular`

This is a **wrapper** skill for `90_System/Skills/process_slack/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --dry-run`
- Summary only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-summary`
- Threads only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-threads`
