# Fireflies → Obsidian meeting transcripts (linking to existing meeting notes)
## Docs
https://docs.fireflies.ai/getting-started/introduction


## Goal
- Pull Fireflies transcripts/summaries after a meeting and attach them to the existing Google-Calendar-created meeting notes in `20_Meetings/YYYY/MM/DD/HHmm - Title.md`.

## Fireflies options (what’s realistic)
- **Polling (recommended, simplest):** periodically fetch transcripts via Fireflies API and update matching meeting notes.
- **Webhooks (best UX, more setup):** Fireflies calls your endpoint when a transcript is ready; your endpoint runs the same “attach transcript to meeting note” logic.
- **Email/Drive exports (manual-ish):** Fireflies sends recap emails or saves to Drive/Notion; you copy/link into the meeting note (hard to automate reliably).

## What to link on the meeting note (stable keys)
Your meeting notes created by `90_System/Skills/gcal_today/gcal_today.py` contain a `## Calendar (auto)` block with:
- `- Meet: ...` (Google Meet / Zoom URL when present)
- `- UID: ...` (stable per occurrence; recurring-safe)
- optionally `- Event: ...` (Google Calendar HTML link)

Fireflies transcripts expose (via API) identifiers that can be used to match:
- `meeting_link` (often the same Meet/Zoom URL)
- `calendar_id` / `cal_id` (calendar provider IDs; recurring-safe in `cal_id`)
- `date` / `dateString` and `title`

## Local integration (implemented here)
Script: `90_System/Skills/fireflies_sync/fireflies_sync.py`

What it does
- Fetches Fireflies transcripts for a date range (default: last 30 days).
- Tries to match each transcript to a meeting note using:
  - `meeting_link` ↔ meeting note `- Meet: ...` (normalized)
  - otherwise `cal_id` / `calendar_id` ↔ meeting note `- UID: ...` (best-effort)
  - otherwise by same-day + nearest start time (fallback)
- Inserts/updates a preserved section in the meeting note (so future Google Calendar sync won’t overwrite it):
  - `## Fireflies (auto)` (inserted just before `## Meeting Notes` if present)

## Setup
- Create your Fireflies API key (Settings → Developer/API in Fireflies).
- Save it locally (gitignored):
  - `90_System/secrets/fireflies_api_key.txt` (one line: the token)
  - or set env var `FIREFLIES_API_KEY`

## Commands (Windows)
- Dry run (prints what it would change):
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --dry-run`
- Sync last 30 days:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync`
- Sync explicit range:
  - `.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --from 2026-01-01 --to 2026-01-31`

## Output format (in the meeting note)
- `## Fireflies (auto)`
  - `- Transcript: ...` (Fireflies transcript URL)
  - `- Fireflies ID: ...`
  - `- Summary: ...` (if available)
  - `- Action items:` bullets (if available)
  - `- Synced: ...`

## If you want webhook-based automation (next step)
- Add a small HTTP endpoint that:
  - verifies Fireflies signature (if you enable signing)
  - receives transcript-ready event
  - runs the same “attach transcript to meeting note” update for that transcript
- Easiest hosting options: Pipedream / Make / Zapier (call local script via a scheduled pull), or a tiny server on a machine with a stable URL.

## Next actions checklist
- [ ] Create Fireflies API key and save it to `90_System/secrets/fireflies_api_key.txt`
- [ ] Run the dry-run command and confirm matches look correct
- [ ] Run the real sync
- [ ] Tell me if you prefer “link only” vs “embed full transcript text” in notes

