---
name: "regular-git-submodules-pull"
description: "Wrapper skill: refresh git submodules in the routine maintenance flow."
---

# Regular Git Submodules Pull

This is a Claude Code mirror of `regular_git_submodules_pull` from `.agents/skills/`.
Original source: `.agents/skills/regular_git_submodules_pull/SKILL.md`
Skill class: `regular`

This is a **wrapper** skill for `90_System/Skills/git_submodules_pull/`.

## Run
- Remote refresh:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\git_submodules_pull\git_submodules_pull.ps1 -Mode remote`
- Pinned reset:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\git_submodules_pull\git_submodules_pull.ps1 -Mode pinned`
