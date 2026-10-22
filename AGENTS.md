# Agent Instructions (Agentic Vault)

Scope: everything in this repository.

## What this repo is
- This is an Obsidian vault (Markdown-first) designed as a reusable second-brain operating system.
- When doing any task, first check relevant local files.
- Prefer Obsidian wikilinks for durable connections between projects, people, areas, and meetings.

## Session bootstrap
- This `AGENTS.md` is loaded automatically. At session start, read `SOUL.md` and the short core `MEMORY.md` from the repo root.
- Read a topic memory file in `90_System/Memory/` only when the task touches that topic (index in `MEMORY.md`).
- For project context, find its journal in `30_Projects/Journal/`; read relevant open commitments and the latest two daily entries, then follow sources as needed. Do not load all journals or the full index.
- Record a lesson only when it is likely to save time or prevent a repeated mistake: cross-task rules go to `MEMORY.md`, topic-specific lessons go to the matching `90_System/Memory/<Topic>.md`. Follow the admission rule in `MEMORY.md`.

## Canonical paths for locally stored data
- Emails live under `00_Mailbox/YYYY/MM/DD`. Email summaries and threads use templates in `00_Mailbox/Templates/`.
- Daily briefs live under `10_DailyBriefs/YYYY/MM/`.
- Meetings live under `20_Meetings/YYYY/MM/DD/`. Each meeting record uses `20_Meetings/Templates/MeetingNote_TEMPLATE.md`.
- Projects live under `30_Projects/<ProjectFolder>/`. Snapshots use `30_Projects/Templates/ProjectSnapshot_TEMPLATE.md`.
- Project journals live in `30_Projects/Journal/<Project>.md`; index `30_Projects/Journal/_Journal.md`. Keep one stable journal per project; use `30_Projects/Templates/ProjectJournal_TEMPLATE.md` for new journals.
- People live under `40_People/`. Each person record uses `40_People/Templates/person_TEMPLATE.md`.
- Areas live under `50_Areas/`.
- Workblocks live under `80_Workblocks/` and carry short-lived task handoff state.

## Where to look first
- Answer from local vault files first; use an external-service skill only for data newer than the last sync or missing locally.

| Question type | First source | Then |
|---|---|---|
| Project status, open items, waiting-on, next steps | `30_Projects/Journal/_Journal.md` | `30_Projects/Journal/<Project>.md`: open commitments + latest two daily entries |
| 1:1 preparation | Journals mentioning the person + the upcoming 1:1 note in `20_Meetings/YYYY/MM/DD/` | Recent `00_Mailbox/YYYY/MM/DD/emails_summary.md` and `slack_summary.md` |
| What was agreed in a past meeting | `20_Meetings/YYYY/MM/DD/` notes; titles often lack the client name, so grep content, `project:` and `speakers:` frontmatter, or follow links from the project journal | `adhoc_fireflies` only when the note has no summary |
| Who someone is | `40_People/<Name>.md` and `40_People/_PeopleIndex.md` | When people share a first name, resolve by surname or email, never by first name |
| Email history or the owner's past wording | `00_Mailbox/YYYY/MM/DD/` summaries and thread snapshots | `adhoc_gmail` for mail newer than the last sync |
| Slack link | Convert `p1700000000123456` to `1700000000_123456` and grep `00_Mailbox/**/slack_*` | `adhoc_slack` when not exported yet |
| Continuing task | `90_System/Skills/workblocks/workblocks.py list --statuses active,blocked --query "<topic>"` | The workblock's key files |
| Codebases | `.gitmodules` (submodules under `30_Projects/`) | Repos the owner names |
| General knowledge or public web question | No vault reading needed | Web search |

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
- Workblocks: `80_Workblocks/<Scope> - <Intent>.md`

## When adding new content
- If the change affects a project, also update `30_Projects/_Projects.md`.
- Journal only new actionable changes: one bullet, one sentence, at most 25 words excluding one source link. Preserve history; do not repeat summaries, unchanged tasks or empty daily entries. Update journal/index status and actions only when they change.
- If the change creates a meeting note, add it to `20_Meetings/_MeetingIndex.md`.
- If the change adds people context, update `40_People/` and `40_People/_PeopleIndex.md`.
- If the change adds or updates an area, reflect it in `50_Areas/_Areas.md`.

## Skill routing
- Skills are available in `.agents/skills/`.
- Claude Code mirrors in `.claude/skills/` use hyphens instead of underscores: `adhoc_gmail` is `adhoc-gmail`.
- Use `regular_*` for deterministic maintenance flows.
- Use `regular_project_journal` for scheduled incremental project journals or the owner's explicit request for the same update; follow its collection runbook. Installing it does not schedule future runs.
- `regular_day_start` ends with `regular_daily_focus` and `regular_day_end` ends with `regular_missed_replies`; both read stored vault files only.
- Send Telegram notifications (`adhoc_send_telegram_notification`) or commit/push (`regular_vault_commit`) only when the routine prompt or the owner asks. Push only to the allow-listed private remote; never pull, merge or force-push to recover a rejected push.
- Scheduled-run prompts live in `90_System/Automations/`.
- Use `bulk_*` for deterministic backfills.
- Use `adhoc_*` for one-off external-system or local-file work.
- Local browser automation is available through `adhoc_browser_playwright`, backed by `90_System/Skills/browser_playwright/`.
- Google Workspace access is available through `adhoc_google_drive`, `gdocs`, `gsheets`, and `gslides`, backed by `90_System/Skills/google_drive_assistant/`.

## Agent deliverables
- Answer ad-hoc questions in chat. Write files, including `70_Exports/` dumps or reports, only when the owner asks for a file or the task is a file edit.
- Prefer actionable checklists at the end of outputs.
- If something is ambiguous, ask 1 to 3 concrete questions.

## Workblock protocol
- At session start, use `90_System/Skills/workblocks/workblocks.py list --statuses active,blocked --query "<current topic>"` to look for continuing work.
- Load at most one clearly relevant workblock and verify its state against the referenced vault files.
- Create a workblock only for work with a real continuation beyond the current session.
- Before the final answer, update the workblock used with verified current state, next action, blockers, and key files.
- End each final response with exactly one workblock receipt: `Workblock: updated <path>`, `Workblock: read, unchanged <path>`, or `Workblock: not needed — one-off task`.

## Deferred task queue
- Deferred queue root: `90_System/TaskQueue/`
- Use this when work should be deferred because the current run cannot or should not finish it now.
- Canonical helper: `90_System/Skills/deferred_task_queue/task_queue.py`


