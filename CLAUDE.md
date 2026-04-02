# Claude Instructions (Agentic Vault)

This file is generated or maintained from the repo-local guidance. Treat `AGENTS.md`, `SOUL.md`, and `MEMORY.md` as the source of truth.

## Startup
- At the start of each session, read `AGENTS.md`, `SOUL.md`, and `MEMORY.md` from the repo root.

## Behavioral defaults
- Preserve the current structure and stay Obsidian-friendly.
- Keep outputs concise and actionable.
- Reuse templates and existing note patterns before inventing new ones.

## Non-negotiables
- Keep external-service access inside dedicated skills.
- Do not delete, move, or rename files unless explicitly asked.
- For outside-vault file edits, work on exported copies under `70_Exports/YYYY/MM/DD/`.

## Repo-local Google skills
- Use `adhoc_google_drive` for Drive file discovery and exports.
- Use `gdocs`, `gsheets`, and `gslides` for repo-local Google document operations through the shared runtime.
