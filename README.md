# Agentic Vault

A reusable, Obsidian-friendly vault skeleton for personal operating systems with repo-local agent skills and automation wrappers.

## Included

- Markdown-first vault structure for mailbox, daily briefs, meetings, projects, people, and areas
- Repo-local Codex and Claude guidance
- Wrapper skills in `.agents/` plus runnable automation code in `90_System/Skills/`
- Task queue, integration docs, and note templates

## Excluded on purpose

- Personal notes, meeting history, people records, and area/project content
- Secrets, OAuth tokens, runtime state, logs, and machine-local settings
- Obsidian workspace state and ad-hoc attachments

## First setup

1. Open the vault in Obsidian.
2. Review and customize `AGENTS.md`, `SOUL.md`, `MEMORY.md`, and `60_SOPs/_HowIWork.md`.
3. Add your own secrets and OAuth files under `90_System/secrets/` without committing them.
4. Install Python dependencies from `requirements.txt` into a local virtual environment.
5. Adjust `.codex/config.toml` if you want this vault to work with additional external repos.
