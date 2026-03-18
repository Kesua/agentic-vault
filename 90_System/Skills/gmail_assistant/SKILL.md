---
name: "adhoc_gmail"
description: "Ad-hoc Gmail assistant: read Gmail safely across `private` and `personal`, create drafts only, and optionally export urgent items, follow-ups, and people updates into the vault."
---

# Gmail assistant

## What it does
- Authenticates to Gmail for `private` and `personal` accounts with OAuth desktop-app flow
- Reads Gmail threads and messages with search-oriented commands:
  - `search`
  - `summarize-thread`
  - `list-unanswered`
  - `list-today`
  - `list-by-person`
- Creates Gmail drafts only:
  - `draft-reply`
  - `draft-followup`
- Optionally writes selected outputs into the vault:
  - urgent items into `[[00_Mailbox/_Mailbox]]`
  - follow-ups into today’s Daily Brief under `# Gmail`
- Never sends mail automatically

## Canonical paths + ownership
- Skill code: `90_System/Skills/gmail_assistant/gmail_assistant.py`
- Wrapper: `.agents/skills/adhoc_gmail/SKILL.md`
- Secrets: `90_System/secrets/`
- Mailbox target: `00_Mailbox/_Mailbox.md`
- Daily Brief target: `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`
- People targets:
  - `40_People/<Person Name>.md`
  - `40_People/_PeopleIndex.md`

## Safety model
- OAuth scopes include Gmail read access and draft creation access
- The skill can download attachments into the vault only on explicit command
- The skill creates drafts in Gmail but does not send mail
- Vault writes happen only when you opt in with command flags

## Setup: Google Cloud / Gmail API

### 1. Create or reuse a Google Cloud project
- For simplest setup, you can reuse one project and one Desktop OAuth client for both inboxes
- If your work Google Workspace policy requires a separate project, use per-account client files instead

### 2. Enable Gmail API
- Open Google Cloud Console
- In the selected project, enable `Gmail API`

### 3. Configure OAuth consent
- In Google Auth Platform, configure:
  - Branding
  - Audience
  - Data Access
- Add your own Google account(s) as test users if the app is not published
- You do not need verification for personal internal use

### 4. Create a Desktop app OAuth client
- Create credentials: `OAuth client ID`
- Application type: `Desktop app`
- Download the client JSON

### 5. Place client JSON in the vault
- Shared client for both accounts:
  - `90_System/secrets/gmail_oauth_client.json`
- Or per-account files:
  - `90_System/secrets/gmail_oauth_client_private.json`
  - `90_System/secrets/gmail_oauth_client_personal.json`

### 6. Authenticate each mailbox
- Work/private mailbox:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py auth --account private`
- Personal mailbox:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py auth --account personal`
- Successful auth creates:
  - `90_System/secrets/gmail_token_private.json`
  - `90_System/secrets/gmail_token_personal.json`

## Recommended account setup
- Use the same naming as `gcal_today`:
  - `private` = work/private Google account
  - `personal` = personal Google account
- This keeps the Google automation stack consistent across Calendar and Gmail

## Browser/account hygiene
- Before auth, make sure you know which Google account is active in the browser
- Best practice:
  - use a dedicated browser profile for work/private
  - use a second profile for personal
- If the wrong account was authorized:
  - delete only the matching token file in `90_System/secrets/`
  - rerun `auth --account ...`

## Commands (Windows)
Run these from the vault root.

- Authenticate:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py auth --account private`
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py auth --account personal`
- Search:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py search --account private --query "from:alice newer_than:30d"`
- Summarize a thread:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py summarize-thread --account private --thread-id <thread_id>`
- Download attachments from a thread into the canonical mailbox path:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py download-attachments --account private --thread-id <thread_id>`
- Download attachments into a chosen folder:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py download-attachments --account private --thread-id <thread_id> --output-dir "00_Mailbox\2026\03\11\attachments\custom"`
- List Inbox threads waiting on your reply:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py list-unanswered --account private`
- List today’s messages:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py list-today --account personal`
- List threads by person/email:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py list-by-person --account private --person "adam.nowak@weareflo.com"`
- Create a reply draft:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py draft-reply --account private --thread-id <thread_id> --body "Thanks, I will reply in detail tomorrow."`
- Create a follow-up draft:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py draft-followup --account personal --to "name@example.com" --subject "Follow-up" --body "Checking in on this."`
## Vault output flags
- Add unanswered follow-ups into Mailbox:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py list-unanswered --account private --to-inbox`
- Add unanswered follow-ups into today’s Daily Brief:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py list-unanswered --account private --to-daily-brief`
- Summarize a thread and export signals:
  - `.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py summarize-thread --account private --thread-id <thread_id> --to-inbox --to-daily-brief`

## How unanswered threads are defined
- Searches `in:inbox`
- Loads each candidate thread
- Ignores draft-only latest activity
- Marks a thread as unanswered when the latest non-draft message was sent by someone else

## Troubleshooting
- `Missing OAuth client file`
  - Put the downloaded Desktop OAuth client JSON into one of the expected `90_System/secrets/` paths
- `Missing/invalid token`
  - Rerun `auth --account private` or `auth --account personal`
- Browser opened with the wrong Google account
  - Delete the matching token file and authenticate again
- Gmail API access denied / app not configured
  - Confirm Gmail API is enabled in the selected Google Cloud project
  - Confirm your account is added as a test user if the app is not published
- `access_denied` in a corporate Google Workspace
  - Your admin may need to allow the OAuth app or you may need a dedicated work project/client
- `Unable to create process using ...WindowsApps...python.exe`
  - Use python.org Python, not the Microsoft Store alias
  - Verify `where.exe python`
  - Recreate `.venv` if needed
- If tokens expire or are revoked
  - delete only the affected `gmail_token_*.json`
  - rerun auth for that one account

## References
- Gmail Python quickstart: https://developers.google.com/workspace/gmail/api/quickstart/python
- Gmail scopes: https://developers.google.com/workspace/gmail/api/auth/scopes
- Gmail drafts API: https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.drafts/create
