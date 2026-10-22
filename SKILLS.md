# Skills

Skills are optional mini-playbooks that the agent can load on demand.

## Skill classes
- `regular_*`: repeatable routines and deterministic file or system changes
- `bulk_*`: deterministic backfills over a caller-provided window
- `adhoc_*`: interactive exploration of external systems and one-off actions

## Where to look
- Wrapper skill docs: `.agents/skills/**/SKILL.md`
- Runnable automation code: `90_System/Skills/**`

## Rule of thumb
- deterministic vault-maintenance flow -> `regular_*`
- deterministic backfill -> `bulk_*`
- exploratory lookup, retrieval, draft, or one-off create action -> `adhoc_*`

## Project journals
- `regular_project_journal`: use for scheduled or explicitly requested incremental journal updates.
  - Skill: `.agents/skills/regular_project_journal/SKILL.md`
  - Collection and progress: `90_System/Skills/project_journal/RUNBOOK.md`
  - Journals: `30_Projects/Journal/`; template: `30_Projects/Templates/ProjectJournal_TEMPLATE.md`

## Daily routine add-ons
- `regular_daily_focus`: last step of `regular_day_start`; writes `# Focus topics for today` into today's brief from yesterday's stored email and Slack.
- `regular_missed_replies`: last step of `regular_day_end`; writes `# Possibly forgotten` into today's brief from today's stored email, Slack and meetings.
- `regular_vault_commit`: commits routine-owned folders; pushes only to an allow-listed private remote.
- `adhoc_send_telegram_notification`: sends one requested summary to the owner's single Telegram chat.
- Scheduled prompts that combine them: `90_System/Automations/`.

## Notable adhoc skills
- `adhoc_browser_playwright`: real Chromium browser workflows for DOM inspection, screenshots, response capture, and browser-gated pages

- dhoc_google_drive: repo-local Google Workspace assistant for Drive search, metadata, and exports
- gdocs: repo-local Google Docs operations through the shared Google workspace runtime
- gsheets: repo-local Google Sheets operations through the shared Google workspace runtime
- gslides: repo-local Google Slides operations through the shared Google workspace runtime

