---
name: "regular-vault-commit"
description: "Routine step: commit only routine-owned vault folders with a standard message, and optionally push to an allow-listed private remote."
---

# Regular Vault Commit

This is a Claude Code mirror of `regular_vault_commit` from `.agents/skills/`.
Original source: `.agents/skills/regular_vault_commit/SKILL.md`
Skill class: `regular`

This is a **wrapper** skill for `90_System/Skills/vault_git/vault_commit.py`. Use it only when the routine prompt or the owner asks to commit (and push) the routine's results.

## Run
- Commit:
  - `.\.venv\Scripts\python.exe 90_System\Skills\vault_git\vault_commit.py --routine day-start`
- Commit and push:
  - `.\.venv\Scripts\python.exe 90_System\Skills\vault_git\vault_commit.py --routine day-end --push`
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\vault_git\vault_commit.py --routine day-end --push --dry-run`

## What it does
- Commits only `00_Mailbox/`, `10_DailyBriefs/`, `20_Meetings/`, `30_Projects/Journal/`, `30_Projects/_Projects.md` and `40_People/` (override with repeated `--path`). Other dirty or staged files stay untouched.
- Uses the message `routine: <routine> <YYYY-MM-DD>`; does nothing when those paths are unchanged.
- Pushes only with `--push`, only the current branch, and only when the remote URL equals `git config agenticvault.pushUrl`.

## One-time setup for push
The vault contains private email, Slack, meeting and people data. Push only to a **private** repository you own, never to the public template you cloned from. After confirming the repository is private, the owner runs once:

- `git remote set-url origin <url of your private vault repository>`
- `git config --local agenticvault.pushUrl <same url>`

## Exit codes and failure handling
- `0` committed or nothing to commit (and pushed, when requested).
- `2` push refused: no allow-listed URL, a different remote, or a detached HEAD. Report the printed setup step.
- `3` push rejected by the remote (usually non-fast-forward). Report ahead/behind counts and stop.
- Never pull, merge, rebase, reset or force-push to recover; reconciliation is the owner's decision.
- A failed commit or push does not undo the routine's results.
