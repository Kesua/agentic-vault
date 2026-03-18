---
name: "adhoc_gmail"
description: "Wrapper skill: read Gmail safely, create drafts only, and optionally export follow-ups and people context into the vault."
---

# Ad-hoc Gmail

This is a **wrapper** skill for the repo automation in `90_System/Skills/gmail_assistant/`.

## Scope
- Search and summarize Gmail threads
- List today’s mail and unanswered Inbox threads
- Download thread attachments into the vault on explicit request
- Create Gmail drafts only
- Optionally export signals into the vault when explicitly requested

## Run (from the vault repo root)
- Authenticate:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py auth --account private`
- Search:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py search --account private --query "from:alice newer_than:30d"`
- Download attachments:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py download-attachments --account private --thread-id <thread_id>`
- Full docs:
  - `90_System/Skills/gmail_assistant/SKILL.md`

