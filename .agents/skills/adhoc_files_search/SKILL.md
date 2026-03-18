---
name: "adhoc_files_search"
description: "Wrapper skill: search the filesystem with explicit agent-passed paths, read-only."
---

# Ad-hoc Filesystem Search

This is a **wrapper** skill for the repo automation in `90_System/Skills/files_search/`.

## Scope
- List files and folders under an explicit path
- Find filesystem entries by name, glob, or extension
- Search inside text files under an explicit path
- Never changes any file or directory

## Rules
- First inspect the relevant project or area note for filesystem context
- Pass the concrete filesystem path explicitly to the command
- Use this skill for read-only discovery only
- Do not use this skill for delete, move, rename, write, copy, or overwrite workflows
- If the user wants a file created or updated, switch to the appropriate document skill and keep any new or edited artifact under `70_Exports/YYYY/MM/DD/`

## Run (from the vault repo root)
- List one folder:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py list --path "C:\work\project"`
- Find Python files recursively:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py find --path "C:\work\project" --ext .py --recursive --limit 50`
- Search text recursively:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py search-text --path "C:\work\project" --query "TODO" --recursive --limit 20`
- Full docs:
  - `90_System/Skills/files_search/SKILL.md`
