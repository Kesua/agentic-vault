# Agent Instructions (Agentic Vault)

Scope: everything in this repository.

## What this repo is
- This is an Obsidian vault (Markdown-first) designed as a reusable second-brain operating system.
- When doing any task, first check relevant local files.
- Prefer Obsidian wikilinks for durable connections between projects, people, areas, and meetings.

## Session bootstrap
- In every session, read `AGENTS.md`, `SOUL.md`, and `MEMORY.md` from the repo root.
- Update `MEMORY.md` only when a new lesson is likely to save time or prevent a repeated mistake.

## Canonical paths for locally stored data
- Emails live under `00_Mailbox/YYYY/MM/DD`. Email summaries and threads use templates in `00_Mailbox/Templates/`.
- Daily briefs live under `10_DailyBriefs/YYYY/MM/`.
- Meetings live under `20_Meetings/YYYY/MM/DD/`. Each meeting record uses `20_Meetings/Templates/MeetingNote_TEMPLATE.md`.
- Projects live under `30_Projects/<ProjectFolder>/`. Snapshots use `30_Projects/Templates/ProjectSnapshot_TEMPLATE.md`.
- People live under `40_People/`. Each person record uses `40_People/Templates/person_TEMPLATE.md`.
- Areas live under `50_Areas/`.

## Non-negotiables
- ABSOLUTELY NEVER USE AVAILABLE TOKENS TO CUSTOM INTERACTION WITH EXTERNAL SERVICES. EXTERNAL SERVICES CAN ONLY BE QUERIED BY DEDICATED SKILLS.
- Prefer stable paths and simple naming conventions.
- Keep any changes Obsidian-friendly.
- Do not delete, move, or rename existing user files unless explicitly asked.
- For local filesystem editing skills, never modify source files in place outside the vault. Read from the selected path, but write new or updated artifacts only under `70_Exports/YYYY/MM/DD/<file_name>`.
- For edits of existing external files, first create a copy in `70_Exports/YYYY/MM/DD/`, edit only that exported copy, and report both the original and exported paths.
- Do not restructure folders unless explicitly asked.
- Default to short bullets over paragraphs.
- Use YAML frontmatter only when it materially helps.

## File naming
- Daily briefs: `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`
- Meetings: `20_Meetings/YYYY/MM/DD/HHmm - Title.md`
- Projects: keep a stable project note name; snapshots use `... - Snapshot` if needed
- People: `40_People/Person Name.md`
- Areas: `50_Areas/Area Name/`

## When adding new content
- If the change affects a project, also update `30_Projects/_Projects.md`.
- If the change creates a meeting note, add it to `20_Meetings/_MeetingIndex.md`.
- If the change adds people context, update `40_People/` and `40_People/_PeopleIndex.md`.
- If the change adds or updates an area, reflect it in `50_Areas/_Areas.md`.

## Skill routing
- Skills are available in `.agents/skills/`.
- Use `regular_*` for deterministic maintenance flows.
- Use `bulk_*` for deterministic backfills.
- Use `adhoc_*` for one-off external-system or local-file work.

## Agent deliverables
- Prefer actionable checklists at the end of outputs.
- If something is ambiguous, ask 1 to 3 concrete questions.

## Deferred task queue
- Deferred queue root: `90_System/TaskQueue/`
- Use this when work should be deferred because the current run cannot or should not finish it now.
- Canonical helper: `90_System/Skills/deferred_task_queue/task_queue.py`
