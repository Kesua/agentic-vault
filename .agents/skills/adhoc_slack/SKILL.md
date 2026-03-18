---
name: "adhoc_slack"
description: "Wrapper skill: read Slack safely, search approved conversations, summarize threads, and optionally export follow-up signals into the vault."
---

# Ad-hoc Slack

This is a **wrapper** skill for `90_System/Skills/slack_assistant/`.

## Run
- Auth check:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py auth-check --workspace private`
- Search:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py search --workspace private --query "incident review"`
- Summarize a thread:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py summarize-thread --workspace private --conversation C12345678 --thread-ts 1710240000.000100`
- Download files from a thread:
  - `.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py download-files --workspace private --conversation C12345678 --thread-ts 1710240000.000100`
- Full docs:
  - `90_System/Skills/slack_assistant/SKILL.md`
