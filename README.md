# Agentic Vault

A reusable, Obsidian-friendly vault skeleton for personal operating systems with repo-local agent skills and automation wrappers.

## Included

- Markdown-first vault structure for mailbox, daily briefs, meetings, projects, people, and areas
- Repo-local Codex, Claude, and OpenCode guidance
- Wrapper skills in `.agents/` plus runnable automation code in `90_System/Skills/`
- Optional Playwright browser tooling installable from the setup wizard
- Repo-local Google Workspace skills for Drive, Docs, Sheets, and Slides
- Task queue, integration docs, and note templates

## Excluded on purpose

- Personal notes, meeting history, people records, and area/project content
- Secrets, OAuth tokens, runtime state, logs, and machine-local settings
- Obsidian workspace state and ad-hoc attachments

## First setup

1. Run `Setup_Windows.bat` on Windows or `Setup_Mac.command` on macOS.
2. The setup wizard checks whether OpenAI Codex, Claude Code, Gemini CLI, or OpenCode is already installed and can configure Google Workspace (Calendar, Gmail, Drive, Docs, Sheets, Slides).
3. If none of them is available, the wizard lets you choose which coding assistant to install and shows the minimum account or license requirement for that option.
4. The wizard can also install optional Playwright browser tooling for browser-first web tasks on Windows and macOS.
5. Review and customize `AGENTS.md`, `SOUL.md`, `MEMORY.md`, and `60_SOPs/_HowIWork.md`.
6. Adjust `.codex/config.toml` if you want this vault to work with additional external repos.
