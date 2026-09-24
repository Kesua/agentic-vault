---
name: "regular-process-slack"
description: "Wrapper skill: export Slack summaries and thread snapshots into `00_Mailbox/` from user-visible conversations."
---

# Regular Process Slack

This is a Claude Code mirror of `regular_process_slack` from `.agents/skills/`.
Original source: `.agents/skills/regular_process_slack/SKILL.md`
Skill class: `regular`

This is a **wrapper** skill for `90_System/Skills/process_slack/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --include-dm --include-mpim`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --dry-run --include-dm --include-mpim`
- Summary only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-summary --include-dm --include-mpim`
- Threads only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-threads --include-dm --include-mpim`

## Notes
- This wrapper includes direct and group messages alongside channels. Use `exclude_conversation_ids` in the local workspace config for conversations to skip.
