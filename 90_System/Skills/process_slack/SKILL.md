---
name: "regular_process_slack"
description: "Regular Slack export: ingest approved Slack conversations into `00_Mailbox/` with daily summaries and thread snapshots."
---

# Process Slack

## What it does
- Reads approved Slack workspaces and allowlisted conversations
- Writes one daily summary note:
  - `00_Mailbox/YYYY/MM/DD/slack_summary.md`
- Writes one latest snapshot per exported thread:
  - `00_Mailbox/YYYY/MM/DD/slack_<workspace>_<conversation>_<thread_ts>.md`
- Replaces older stored instances of the same Slack thread so only the latest snapshot remains
- Persists sync checkpoints in `90_System/Integrations/slack/runtime/`

## Commands
- Run both exports:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --dry-run`
- Initial load / backfill:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --days-back 14`
- Summary only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-summary`
- Threads only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-threads`

## Notes
- Uses the Slack config and token setup documented in `90_System/Skills/slack_assistant/SKILL.md`
- Summary files use `00_Mailbox/Templates/SlackSummary_TEMPLATE.md`
- Thread files use `00_Mailbox/Templates/SlackThread_TEMPLATE.md`
- DMs and group DMs are excluded unless the command includes `--include-dm` and `--include-mpim`
