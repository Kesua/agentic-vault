---
name: "regular_daily_brief_todoist"
description: "Regular Todoist sync: write due tasks into Daily Briefs, replacing only the `# Tasks` section."
---

# Todoist -> Daily Brief Tasks (14 days)

## What it does
- Reads personal Todoist API token from `90_System/secrets/todoist_token_personal.json`
- Fetches active Todoist tasks
- Filters tasks by due date for `today` through `today + 14 days` (inclusive)
- Creates/updates daily brief files in `10_DailyBriefs/YYYY/MM/`
- Replaces only the `# Tasks` section in each file; preserves all other sections/content
- Writes task details as readable bullets + raw JSON for each task

## Canonical path + ownership
- Daily Brief path: `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`
- This skill owns only the `# Tasks` section.
- `90_System/Skills/Web_Daily_Brief/` owns `# Daily News`.
- `60_SOPs/Templates/DailyBrief_TEMPLATE.md` is the human template reference for the rest of the note.

## Prereqs (local)
- Token file exists: `90_System/secrets/todoist_token_personal.json`
- Token JSON format:
  - `{"token":"<todoist_api_token>"}`

## Commands (Windows)
- Sync daily briefs:
  - `.\.venv\Scripts\python 90_System\Skills\daily_brief_todoist\daily_brief_todoist.py sync`
- Dry run:
  - `.\.venv\Scripts\python 90_System\Skills\daily_brief_todoist\daily_brief_todoist.py sync --dry-run`
- Custom range:
  - `.\.venv\Scripts\python 90_System\Skills\daily_brief_todoist\daily_brief_todoist.py sync --days-ahead 14`

## Output files
- `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`

## Filtering rules
- Includes active tasks with `due.date` exactly equal to each target date
- Target range is today through 14 days ahead (inclusive)
- Excludes tasks without `due.date`

## Update behavior
- If daily brief exists:
  - Replace only `# Tasks` section
  - Preserve all other content
- If daily brief does not exist:
  - Create file with `# Tasks` section only (no frontmatter)

## Recommended workflow
- Use `.agents/skills/regular_day_start/SKILL.md` when you want the full morning flow.
- After project or people alias changes, run `regular_create_links` so Daily Brief mentions can be relinked.

## References
- Official Python SDK: https://github.com/Doist/todoist-api-python/
- SDK documentation: https://doist.github.io/todoist-api-python/
- API documentation: https://developer.todoist.com/api/v1/#section/Developing-with-Todoist
