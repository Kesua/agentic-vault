---
name: "regular_git_submodules_pull"
description: "Regular repository maintenance: initialize and refresh all git submodules in this vault."
---

# Git: Pull all submodules

## What it does
- Syncs submodule URLs from `.gitmodules`
- Initializes submodules if missing
- Updates all submodules recursively
- Optionally updates submodules to latest remote commits (records new SHAs in the vault repo as changes to commit)

## Commands (Windows)
- Pull latest from configured remotes (recommended, PowerShell):
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\git_submodules_pull\git_submodules_pull.ps1 -Mode remote`
- Reset working tree to the SHAs pinned by the vault repo (no remote tracking, PowerShell):
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\git_submodules_pull\git_submodules_pull.ps1 -Mode pinned`
- Dry run (PowerShell):
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\git_submodules_pull\git_submodules_pull.ps1 -Mode remote -DryRun`

## Alternative (Python)
- Pull latest from configured remotes:
  - `.\.venv\Scripts\python 90_System\Skills\git_submodules_pull\git_submodules_pull.py sync --mode remote`
- Reset working tree to pinned SHAs:
  - `.\.venv\Scripts\python 90_System\Skills\git_submodules_pull\git_submodules_pull.py sync --mode pinned`

## Notes
- After `--mode remote`, the vault repo will show submodule pointer updates in `git status`. Commit those in the vault repo to record the new submodule SHAs.
