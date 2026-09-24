---
name: "adhoc_slack"
description: "Ad-hoc Slack assistant: inspect user-visible conversations, summarize threads, download eligible files, and export follow-up signals into the vault."
---

# Slack assistant

## What it does
- Validates Slack user auth against a configured workspace alias
- Reads conversations visible to the token owner
- Searches accessible conversations by scanning recent thread content
- Summarizes a thread and can optionally append signals into `[[00_Mailbox/_Mailbox]]` or today’s Daily Brief
- Downloads Slack files only when workspace policy allows it
- Keeps future write commands as explicit placeholders only

## Canonical paths + ownership
- Skill code: `90_System/Skills/slack_assistant/slack_assistant.py`
- Batch export: `90_System/Skills/process_slack/process_slack.py`
- Wrapper: `.agents/skills/adhoc_slack/SKILL.md`
- Config: `90_System/Integrations/slack/workspaces.json`
- Config example: `90_System/Integrations/slack/workspaces.example.json`
- Read app manifest: `90_System/Integrations/slack/app_manifest.readonly.yaml`
- Future write app manifest: `90_System/Integrations/slack/app_manifest.writefuture.yaml`
- Secret: `90_System/secrets/slack_user_token_<workspace>.txt`
- Runtime state: `90_System/Integrations/slack/runtime/`

## Safety model
- Automated sync reads all user-visible channels plus DMs/group DMs when explicitly included by flags
- Tokens stay in `90_System/secrets/` and are never written to notes
- File downloads are blocked unless enabled globally and for a specific conversation
- Draft/write commands are placeholders and fail closed until a separate write-capable app is configured

## Setup
1. Create a Slack app from `90_System/Integrations/slack/app_manifest.readonly.yaml`
2. Install it into the target workspace
3. Copy the Slack User OAuth Token into `90_System/secrets/slack_user_token_<workspace>.txt`
4. Copy `90_System/Integrations/slack/workspaces.example.json` to `90_System/Integrations/slack/workspaces.json`
5. Fill in workspace alias, team ID, and the token owner's `self_user_ids`
6. Validate with:
   - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py auth-check --workspace private`
7. Optionally add `exclude_conversation_ids` in `workspaces.json` to skip specific conversations

## Commands
- Auth check:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py auth-check --workspace private`
- List accessible conversations:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py list-conversations --workspace private`
- Search accessible threads:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py search --workspace private --query "handover" --days-back 14`
- Summarize one thread:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py summarize-thread --workspace private --conversation C12345678 --thread-ts 1710240000.000100`
- Add a summarized thread into Inbox and Daily Brief:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py summarize-thread --workspace private --conversation C12345678 --thread-ts 1710240000.000100 --to-inbox --to-daily-brief`
- List unanswered threads:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py list-unanswered --workspace private --include-dm --include-mpim`
- List threads by person/email:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py list-by-person --workspace private --person "alice@example.com"`
- Download files from an approved thread:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py download-files --workspace private --conversation C12345678 --thread-ts 1710240000.000100`

## Notes
- Search works by scanning recent channel and DM thread content, not by using Slack global search
- The export workflow treats Slack as inbound communication and writes into `00_Mailbox/YYYY/MM/DD/`
- Read sync uses the Slack user token as its credential
- `exclude_conversation_ids` removes matching conversations from automatic discovery, search, and sync
- `draft-message` and `draft-reply` intentionally return a gated error until a separate write app exists
