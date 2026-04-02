---
name: "adhoc_google_drive"
description: "Ad-hoc Google Drive assistant: search Drive and inspect Docs, Sheets, and Slides across `private` and `personal` accounts."
---

# Google Drive assistant

## What it does
- Authenticates to Google Workspace for `private` and `personal` accounts with OAuth desktop-app flow
- Searches Google Drive across one or both accounts
- Reads file metadata from Drive
- Reads and updates Google Docs content, ranges, and simple tables
- Reads and updates Google Sheets metadata, ranges, and appended rows
- Reads and updates Google Slides text and can create presentations
- Exports or downloads files into the vault on explicit command

## Canonical paths + ownership
- Skill code: `90_System/Skills/google_drive_assistant/google_drive_assistant.py`
- Wrapper: `.agents/skills/adhoc_google_drive/SKILL.md`
- Secrets: `90_System/secrets/`
- Export target: `70_Exports/YYYY/MM/DD/`

## Safety model
- OAuth scopes cover Google Workspace read and write operations for Drive, Docs, Sheets, and Slides
- Google file writes happen only through explicit commands
- Export/download still writes only into the vault
- Multi-account access follows the same `private` / `personal` pattern already used by `gcal_today` and `gmail_assistant`

## Setup: Google Cloud / Drive APIs

### 1. Create or reuse a Google Cloud project
- For simplest setup, reuse one Desktop OAuth client for both accounts
- If your work account needs separate governance, use per-account client files

### 2. Enable APIs
- Enable:
  - `Google Drive API`
  - `Google Docs API`
  - `Google Sheets API`
  - `Google Slides API`

### 3. Configure OAuth consent
- Configure Branding, Audience, and Data Access
- Add both Google accounts as test users if the app is not published

### 4. Create a Desktop app OAuth client
- Create `OAuth client ID`
- Application type: `Desktop app`
- Download the client JSON

### 5. Place client JSON in the vault
- Shared client for both accounts:
  - `90_System/secrets/gdrive_oauth_client.json`
- Or per-account files:
  - `90_System/secrets/gdrive_oauth_client_private.json`
  - `90_System/secrets/gdrive_oauth_client_personal.json`

### 6. Authenticate each account
- Private/work:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py auth --account private`
- Personal:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py auth --account personal`
- Successful auth creates:
  - `90_System/secrets/gdrive_token_private.json`
  - `90_System/secrets/gdrive_token_personal.json`

## Commands (Windows)
Run these from the vault root.

- Authenticate:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py auth --account private`
- Search across both accounts:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py search --account both --query "quarterly plan"`
- Search only presentations:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py search --account both --type presentation --query "board review"`
- List recent files:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py recent --account both`
- List a folder:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py list-folder --account private --folder-id <folder_id>`
- Get Drive metadata:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-metadata --account both --file-id <file_id_or_url>`
- Read a Google Doc:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-doc-text --account both --document-id <doc_id_or_url>`
- Inspect a spreadsheet:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-sheet-metadata --account both --spreadsheet-id <sheet_id_or_url>`
- Read spreadsheet values:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-sheet-values --account both --spreadsheet-id <sheet_id_or_url> --sheet-name "Sheet1" --range "A1:D20"`
- Read presentation text:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-presentation-text --account both --presentation-id <presentation_id_or_url>`
- Export/download a file into the vault:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py export-file --account both --file-id <file_id_or_url>`

## Notes on scope
- This first version mirrors the repo-native pattern used by Gmail and GCal and covers the highest-value read operations
- It is not yet a full replacement for the desktop Google Drive plugin's document editing APIs
- If needed, it can be extended later with write flows for Docs, Sheets, or Slides using the same per-account credential model

## Troubleshooting
- `Missing OAuth client file`
  - Put the downloaded Desktop OAuth client JSON into one of the expected `90_System/secrets/` paths
- `Missing/invalid token`
  - Rerun `auth --account private` or `auth --account personal`
- Wrong Google account opened in the browser
  - Delete the matching `gdrive_token_*.json` and authenticate again
- `access_denied`
  - Confirm the account is listed as an OAuth test user
  - Confirm the required APIs are enabled in the selected Google Cloud project

## References
- Drive API quickstart: https://developers.google.com/workspace/drive/api/quickstart/python
- Docs API overview: https://developers.google.com/docs/api
- Sheets API overview: https://developers.google.com/workspace/sheets/api
- Slides API overview: https://developers.google.com/workspace/slides/api

## Additional edit commands
- `get-doc-structure`, `find-doc-text`, `replace-doc-range`, `append-doc-table`
- `find-sheet-rows`, `update-sheet-values`, `append-sheet-rows`
- `create-presentation`, `replace-slide-text`, `update-slide-shape-text`

