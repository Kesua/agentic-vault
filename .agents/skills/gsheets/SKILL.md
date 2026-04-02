---
name: "gsheets"
description: "Repo-local Google Sheets skill: inspect tabs and ranges, search rows, update values, and append structured rows."
---

# Google Sheets

This is a **repo-local** Google Sheets skill backed by `90_System/Skills/google_drive_assistant/google_drive_assistant.py`.

## Scope
- Read spreadsheet metadata and values
- Search rows by plain-text query inside a range
- Update a target range with raw or formula values
- Append rows to a sheet

## Run (from the vault repo root)
- Inspect metadata:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-sheet-metadata --account both --spreadsheet-id <sheet_id_or_url>`
- Read values:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-sheet-values --account both --spreadsheet-id <sheet_id_or_url> --sheet-name "Sheet1" --range "A1:D20"`
- Find rows:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py find-sheet-rows --account both --spreadsheet-id <sheet_id_or_url> --sheet-name "Sheet1" --range "A1:Z200" --query "Jan"`
- Update a range:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py update-sheet-values --account both --spreadsheet-id <sheet_id_or_url> --range "Sheet1!A2:C2" --values-json '[["Jan","Open","=TODAY()"]]'`
- Append rows:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py append-sheet-rows --account both --spreadsheet-id <sheet_id_or_url> --sheet-name "Sheet1" --rows-json '[["Jan","Review","Pending"]]'`
- Full docs:
  - `90_System/Skills/google_drive_assistant/SKILL.md`
