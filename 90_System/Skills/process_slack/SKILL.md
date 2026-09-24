---
name: "regular_process_slack"
description: "Regular Slack export: ingest user-visible Slack conversations into `00_Mailbox/` with daily summaries and thread snapshots."
---

# Process Slack

## What it does
- Reads Slack conversations visible to the token owner in the configured workspace
- Writes one daily summary note:
  - `00_Mailbox/YYYY/MM/DD/slack_summary.md`
- Writes one latest snapshot per exported thread:
  - `00_Mailbox/YYYY/MM/DD/slack_<workspace>_<conversation>_<thread_ts>.md`
- Replaces older stored instances of the same Slack thread so only the latest snapshot remains
- Persists sync checkpoints in `90_System/Integrations/slack/runtime/`

## Commands
- Run both exports:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --include-dm --include-mpim`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --dry-run --include-dm --include-mpim`
- Initial load / backfill:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --days-back 14 --include-dm --include-mpim`
- Summary only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-summary --include-dm --include-mpim`
- Threads only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync-threads --include-dm --include-mpim`

## Notes
- Uses the Slack config and token setup documented in `90_System/Skills/slack_assistant/SKILL.md`
- Summary files use `00_Mailbox/Templates/SlackSummary_TEMPLATE.md`
- Thread files use `00_Mailbox/Templates/SlackThread_TEMPLATE.md`
- The routine wrapper includes `--include-dm` and `--include-mpim` so direct and group messages are exported alongside channels
