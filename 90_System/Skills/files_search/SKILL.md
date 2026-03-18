---
name: "files_search"
description: "Read-only filesystem search helper with explicit caller-passed paths."
---

# Filesystem Search

## What it does
- Lists files and directories for an explicit path
- Finds matching filesystem entries by exact name, glob, or extension
- Searches inside text files without editing anything
- Works both inside and outside the vault

## Safety model
- Read-only only
- No file creation, modification, rename, copy, or deletion commands
- The caller must pass the path explicitly
- The script validates that the path exists before traversal

## Canonical paths
- Skill code: `90_System/Skills/files_search/files_search.py`
- Wrapper: `.agents/skills/adhoc_files_search/SKILL.md`

## Commands (Windows)
- List entries:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py list --path "C:\work\project"`
- List recursively up to depth 2:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py list --path "C:\work\project" --recursive --max-depth 2`
- Find by exact filename:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py find --path "C:\work\project" --name "README.md"`
- Find by glob:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py find --path "C:\work\project" --glob "*.py" --recursive`
- Find by extension:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py find --path "C:\work\project" --ext .md --recursive`
- Search text:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py search-text --path "C:\work\project" --query "roadmap" --recursive`
- JSON output:
  - `.\.venv\Scripts\python.exe 90_System\Skills\files_search\files_search.py find --path "C:\work\project" --ext .ts --recursive --json`

## Notes
- `list` expects a directory path
- `find` and `search-text` accept either a directory or a single file path
- Hidden entries are skipped by default unless `--include-hidden` is provided
- Text search skips binary and unreadable files
