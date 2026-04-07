# Agentic Vault

A reusable, Obsidian-friendly vault skeleton for a personal operating system — with repo-local agent skills, an automated setup wizard, and optional local AI integration.

## What's included

- **Vault structure** — Markdown-first folders for mailbox, daily briefs, meetings, projects, people, and areas
- **Agent guidance** — Repo-local config for Claude Code, Codex, Gemini CLI, and OpenCode (`AGENTS.md`, `SOUL.md`, `CLAUDE.md`, `.codex/`)
- **Skills library** — Wrapper skills in `.agents/` and runnable automation in `90_System/Skills/`:
  - Google Workspace: Calendar, Gmail, Drive, Docs, Sheets, and Slides
  - Playwright browser automation (optional install)
  - Fireflies transcript sync
  - Design review and build skills
  - Task queue and deferred-task workflows
- **Local AI setup** — Wizard-assisted install and configuration of LM Studio or Ollama with model selection and OpenCode integration
- **Note templates** — Meeting notes, project snapshots, people records, and daily briefs

## What's excluded

- Personal notes, meeting history, people records, and area/project content
- Secrets, OAuth tokens, runtime state, logs, and machine-local settings
- Obsidian workspace state and ad-hoc attachments

## Prerequisites

- **Python 3.9+** — the setup wizard auto-installs via `winget` on Windows or Homebrew on macOS if missing
- **Obsidian** (recommended) — open the vault root as a vault; no plugins required for core functionality
- **A coding assistant** — one of: Claude Code, OpenAI Codex, Gemini CLI, or OpenCode (the wizard can install any of them)

## Installation

### Windows

1. Clone or download this repository.
2. Double-click **`Setup_Windows.bat`**.
3. The wizard opens automatically in your browser — follow the on-screen steps.
4. Press `Ctrl+C` in the terminal when you are done.

> If PowerShell blocks the script, run once in PowerShell:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`
> Then double-click `Setup_Windows.bat` again.

### macOS / Linux

1. Clone or download this repository.
2. Double-click **`Setup_Mac.command`** in Finder, **or** run in a terminal:
   ```bash
   bash _setup/bootstrap_mac.sh
   ```
3. The wizard opens automatically in your browser — follow the on-screen steps.
4. Press `Ctrl+C` in the terminal when you are done.

> If macOS says "permission denied", run once:
> `chmod +x Setup_Mac.command _setup/bootstrap_mac.sh`

### What the wizard configures

| Step | What it does |
|------|-------------|
| Coding assistant | Detects or installs Claude Code, Codex, Gemini CLI, or OpenCode |
| Google Workspace | OAuth setup for Calendar, Gmail, Drive, Docs, Sheets, and Slides |
| Local AI | Optional LM Studio or Ollama install with model selection and OpenCode integration |
| Playwright | Optional Chromium-based browser automation tooling |

## After setup

1. Open the vault root in Obsidian.
2. Review and personalize the four core files:
   - `AGENTS.md` — agent routing and canonical paths
   - `SOUL.md` — agent personality and behavioral defaults
   - `MEMORY.md` — persistent lessons and preferences (read by the agent every session)
   - `60_SOPs/_HowIWork.md` — your personal working style
3. Adjust `.codex/config.toml` if you want this vault to reference additional external repos.
4. Start a Claude Code (or your chosen assistant) session in the vault root — the agent reads `AGENTS.md`, `SOUL.md`, and `MEMORY.md` automatically at the start of each session.

## Folder structure

```
00_Mailbox/        Email summaries and threads
10_DailyBriefs/    Daily brief notes
20_Meetings/       Meeting notes (with templates)
30_Projects/       Project notes and snapshots
40_People/         People records
50_Areas/          Area-level notes
60_SOPs/           Standard operating procedures
70_Exports/        Scratch space for exported and edited external files
90_System/         Skills, task queue, secrets (git-ignored), and system docs
_setup/            Bootstrap scripts
src/               Setup wizard source code
```
