# Agentic Vault

A reusable, Obsidian-friendly vault skeleton for personal operating systems with repo-local agent skills and automation wrappers.

## Included

- Markdown-first vault structure for mailbox, daily briefs, meetings, projects, people, and areas
- Repo-local Codex, Claude, and OpenCode guidance
- Wrapper skills in `.agents/` plus runnable automation code in `90_System/Skills/`
- Task queue, integration docs, and note templates

## Excluded on purpose

- Personal notes, meeting history, people records, and area/project content
- Secrets, OAuth tokens, runtime state, logs, and machine-local settings
- Obsidian workspace state and ad-hoc attachments

## First setup

1. Run `Setup_Windows.bat` on Windows or `Setup_Mac.command` on macOS.
2. The setup wizard checks whether OpenAI Codex, Claude Code, or OpenCode is already installed.
3. If none is available, the wizard installs OpenAI Codex for you.
4. Review and customize `AGENTS.md`, `SOUL.md`, `MEMORY.md`, and `60_SOPs/_HowIWork.md`.
5. Adjust `.codex/config.toml` if you want this vault to work with additional external repos.
