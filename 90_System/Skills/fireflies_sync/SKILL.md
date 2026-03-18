---
name: "regular_fireflies_sync"
description: "Regular Fireflies sync: fetch transcript summaries in a date window and upsert them into matching meeting notes."
---

# Fireflies → meeting notes sync

## What it does
- Pulls transcripts via Fireflies GraphQL API (`Authorization: Bearer ...`)
- Matches each transcript to an existing meeting note in `20_Meetings/YYYY/MM/DD/` (does not create notes)
- Upserts exactly one `## Fireflies (auto)` block per meeting note (safe from `gcal_today` overwrites because it is inserted in the preserved tail)
- If multiple transcripts map to the same note, selects one “best” transcript and attaches only that one

## Matching rules (current)
- Uses these fields from meeting notes (usually under `## Calendar (auto)`):
  - `- Meet: ...`
  - `- UID: ...`
  - `- GCal cal_id: ...` (recommended; added by `gcal_today`)
- Uses these fields from Fireflies transcripts: `meeting_link`, `calendar_id`, `cal_id`
- Pairing priority:
  - Unique `- Meet:` match → pair
  - Otherwise exact `- GCal cal_id:` == transcript `cal_id` → pair
  - Otherwise strong `- UID:` match → pair
  - Otherwise → unmatched
- Recurring meetings (same `- Meet:` in multiple notes):
  - Prefer `- GCal cal_id:` or `- UID:` to disambiguate
  - If Fireflies returns only the shared Meet link, use a strict nearest-time fallback only when there is exactly one same-link note within 2 hours

## Prereqs (local)
- Fireflies API key stored in one of:
  - Env var: `FIREFLIES_API_KEY`
  - File: `90_System/secrets/fireflies_api_key.txt` (one line)
- Optional endpoint override (rare): `FIREFLIES_GRAPHQL_ENDPOINT`
- Best results for recurring meetings:
  - Run `gcal_today` first so notes include `- GCal cal_id: ...`

## Optional (recommended when duplicates happen)
- To prefer "my" recording when there are duplicates, set one (or both) env vars (comma-separated):
  - `FIREFLIES_PREFERRED_CALENDAR_IDS`
  - `FIREFLIES_PREFERRED_CAL_IDS`

## Commands (Windows)
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --dry-run`
- Sync last 30 days:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync`
- Sync explicit range:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --from 2026-01-01 --to 2026-01-31`
- Sync last N days:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --days-back 30`

## Notes
- `--dry-run` still calls the Fireflies API; it only prevents writing to files.
- The script scans meeting notes a bit wider than the transcript window (meeting notes range = `from-14d .. to`).
- `--days-back` cannot be combined with `--from` or `--to`.
- Bulk wrapper: `.agents/skills/bulk_sync_fireflies/SKILL.md`
