---
name: "adhoc_google_drive"
description: "Wrapper skill: search Google Drive and inspect Docs, Sheets, and Slides across multiple accounts."
---

# Ad-hoc Google Drive

This is a **wrapper** skill for the repo automation in `90_System/Skills/google_drive_assistant/`.

## Scope
- Search Google Drive across `private`, `personal`, or both accounts
- Inspect one Drive file's metadata
- Read Docs, Sheets, and Slides content
- Export/download a selected file into the vault on explicit request

## Run (from the vault repo root)
- Authenticate:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py auth --account private`
- Search:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py search --account both --query "quarterly plan"`
- Read a Google Doc:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-doc-text --account both --document-id <doc_id_or_url>`
- Full docs:
  - `90_System/Skills/google_drive_assistant/SKILL.md`
