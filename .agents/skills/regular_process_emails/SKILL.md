---
name: "regular_process_emails"
description: "Wrapper skill: export important emails and replied-to threads into the mailbox."
---

# Regular Process Emails

This is a **wrapper** skill for `90_System/Skills/process_emails/`.

## Run
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync --dry-run`
