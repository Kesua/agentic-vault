---
name: "bulk-sync-slack"
description: "Wrapper skill: backfill Slack summaries and thread snapshots for a caller-provided day window."
---

# Bulk Sync Slack

This is a Claude Code mirror of `bulk_sync_slack` from `.agents/skills/`.
Original source: `.agents/skills/bulk_sync_slack/SKILL.md`
Skill class: `bulk`

This is a **wrapper** skill for `90_System/Skills/process_slack/`.

## Run
- Backfill:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --days-back 14`
- Backfill with DMs:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --days-back 14 --include-dm --include-mpim`
