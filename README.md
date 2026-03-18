# Agentic Vault

A reusable, Obsidian-friendly vault skeleton for personal operating systems with repo-local agent skills and automation wrappers.

## What the key files do

This repository includes a few important files in the root folder.

They help the AI assistant behave correctly inside this vault.

### `AGENTS.md`

This is the main instruction file for the AI agent.

It explains:

- what this repository is
- where important types of notes belong
- what rules must never be broken
- how new notes should be named
- which folders are used for projects, people, meetings, and daily briefs

In simple terms:

- `AGENTS.md` tells the AI how to work in this vault safely and consistently

### `SOUL.md`

This file defines the default working style of the AI.

It explains the tone and behavior the AI should follow, for example:

- be pragmatic
- keep things concise
- preserve the current structure
- make the smallest useful change

In simple terms:

- `SOUL.md` describes the AI assistant's personality and working style

### `MEMORY.md`

This file stores durable lessons for future sessions.

It is not a diary.
It is a short list of useful things the AI should remember so it does not repeat mistakes.

Examples:

- preferences about writing style
- rules worth remembering
- repeated pitfalls to avoid

In simple terms:

- `MEMORY.md` is the AI's short long-term memory for this vault

## How the vault is organized

This repository is an Obsidian vault.

That means most important content is stored as normal Markdown files inside clearly named folders.

### Main folder structure

- `00_Mailbox/`
  - saved email and Slack summaries
- `10_DailyBriefs/`
  - one daily brief note per day
- `20_Meetings/`
  - meeting notes, usually created from Google Calendar
- `30_Projects/`
  - project notes and project snapshots
- `40_People/`
  - notes about people
- `50_Areas/`
  - long-term responsibility areas
- `60_SOPs/`
  - guides, templates, and operating procedures
- `70_Exports/`
  - exported or generated files
- `90_System/`
  - system helpers, skills, integrations, logs, and secrets

### The most important technical folders

- `90_System/Skills/`
  - the actual helper tools that connect this vault to outside services such as Google Calendar, Gmail, Todoist, Slack, Fireflies, and Clockify
- `90_System/Integrations/`
  - extra integration setup and runtime files
- `90_System/secrets/`
  - your local secrets, tokens, and OAuth files
  - this folder is private and should never be committed
- `.agents/`
  - wrapper skills and agent-specific helpers

## How to start working in this repository

If you are a non-technical user, the easiest start is:

1. Install Obsidian.
2. Open this folder as an Obsidian vault.
3. Read `how to initialize.md`.
4. Create `90_System/secrets/`.
5. Connect only the services you actually need first.

Recommended first services:

1. Google Calendar
2. Gmail
3. Todoist

That already unlocks a big part of the vault.

## How to work with the AI in this vault

When you ask Claude or Codex to help you here, it uses the vault rules and skills to work safely.

Good examples of requests:

- "Create meeting notes from my calendar"
- "Summarize today's important emails"
- "Sync my Todoist tasks into daily briefs"
- "Help me organize this project note"

The AI will use the correct folder structure and, when needed, the matching skill for that service.

## How permissions work for Claude and Codex

Claude and Codex do not have unlimited freedom inside this repository.

They work under permission rules.

These rules decide things like:

- which folders the AI may read
- which folders the AI may edit
- which folders are blocked
- whether the AI may use the network
- whether the AI must ask before doing more sensitive actions

### Why this matters

This protects the vault from accidental damage.

It also helps keep private material, such as secrets and tokens, out of normal edits.

### Where Claude permissions are stored

Claude's repository-level permission rules are stored in:

- `.claude/settings.json`

In this repository, that file blocks Claude from reading or editing some sensitive places, including:

- `90_System/secrets/`
- `.git/`
- `.venv/`
- `.obsidian/`

It also allows a small set of safe Git inspection commands such as:

- `git status`
- `git diff`
- `git log`
- `git show`

### Where Codex permissions are stored

Codex settings are stored in:

- `.codex/config.toml`

In this repository, that file currently says:

- Codex works in `workspace-write` mode
  - this means it can work inside the repository, but not freely anywhere else on the computer
- network access is enabled
- approval policy is `on-request`
  - this means Codex may need to ask before doing actions outside its normal safe sandbox

### What this means in normal use

In practice:

- the AI can usually read and edit normal vault files
- the AI should not casually read or rewrite your private secret files
- the AI may need approval before more sensitive operations
- the AI follows both the repository instructions and the permission configuration files

### The most important permission locations

- `.claude/settings.json`
  - Claude allow and deny rules
- `.codex/config.toml`
  - Codex sandbox and approval settings
- `AGENTS.md`
  - behavioral rules for the AI inside this repository
- `90_System/secrets/`
  - private local secrets that should stay protected

## Where to go next

- For setup instructions:
  - see `how to initialize.md`
- For AI behavior rules:
  - see `AGENTS.md`, `SOUL.md`, and `MEMORY.md`
- For service-specific helper tools:
  - see `90_System/Skills/`
