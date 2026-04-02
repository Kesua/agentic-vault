---
name: "gdocs"
description: "Repo-local Google Docs skill: inspect document structure, find indexes, update sections, and work with tables."
---

# Google Docs

This is a **repo-local** Google Docs skill backed by `90_System/Skills/google_drive_assistant/google_drive_assistant.py`.

## Scope
- Read Google Doc structure with paragraph and table indexes
- Find text occurrences and index ranges inside a document
- Replace an indexed content range with new text
- Apply a basic named paragraph style to inserted text
- Append a table to the end of a document

## Run (from the vault repo root)
- Inspect structure:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-doc-structure --account both --document-id <doc_id_or_url>`
- Find text:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py find-doc-text --account both --document-id <doc_id_or_url> --query "Q3 plan"`
- Replace a range:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py replace-doc-range --account both --document-id <doc_id_or_url> --start-index 120 --end-index 180 --text "Updated paragraph" --named-style HEADING_2`
- Append a table:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py append-doc-table --account both --document-id <doc_id_or_url> --rows-json '[["Owner","Next step"],["Jan","Review draft"]]'`
- Full docs:
  - `90_System/Skills/google_drive_assistant/SKILL.md`
