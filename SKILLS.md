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

## Notable adhoc skills
- `adhoc_browser_playwright`: real Chromium browser workflows for DOM inspection, screenshots, response capture, and browser-gated pages

- dhoc_google_drive: repo-local Google Workspace assistant for Drive search, metadata, and exports
- gdocs: repo-local Google Docs operations through the shared Google workspace runtime
- gsheets: repo-local Google Sheets operations through the shared Google workspace runtime
- gslides: repo-local Google Slides operations through the shared Google workspace runtime

