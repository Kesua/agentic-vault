---
name: "regular_process_emails"
description: "Regular mailbox export: ingest Gmail into `00_Mailbox/` with daily summaries and latest replied-thread snapshots."
---

# Process emails

## What it does
- Reads both `private` and `personal` Gmail accounts
- Writes one daily summary note:
  - `00_Mailbox/YYYY/MM/DD/emails_summary.md`
- Writes one latest snapshot per thread where you sent at least one message in the last 72 hours:
  - `00_Mailbox/YYYY/MM/DD/<thread_id>_<subject>.md`
- Replaces older stored instances of the same thread so only the latest snapshot remains

## Commands (Windows)
- Run both exports:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync --dry-run`
- Initial load / backfill:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync --days-back 14`
- Summary only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync-important`
- Sent threads only:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync-sent-threads`

## Notes
- Uses the same Gmail OAuth client/token setup as `gmail_assistant`
- Summary files use `00_Mailbox/Templates/EmailSummary_TEMPLATE.md`
- Thread files use `00_Mailbox/Templates/EmailThread_TEMPLATE.md`
- Project linking and people discovery can operate on the stored mailbox files after export
- `--days-back N` backfills historical mail for initial load; summaries are written into each day’s folder in the requested range
- Bulk wrapper: `.agents/skills/bulk_sync_gmail/SKILL.md`
