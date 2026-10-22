# MEMORY

Core working memory, read at the start of every agent session. Keep it short (target under
6,000 characters): only preferences, rules, and pointers that apply across tasks.
Topic-specific lessons go to `90_System/Memory/<Topic>.md`, read only when relevant.
Delete or replace the placeholder lines below with your own.

---

## Preferences

<!-- How you want the agent to communicate and behave by default. Examples:
- Always reply in English.
- Keep responses to three bullets or fewer.
- Never use emojis.
-->
- Keep bullets short and operational.

## Learned Rules

<!-- Durable cross-task lessons from past sessions. Add a bullet only when a correction
     applies to many kinds of tasks; tool- or topic-specific lessons belong in a topic
     file below. Remove rules that are no longer relevant.
-->
- Prefer wrapper skills over direct external-service access.
- Keep runtime state, logs, and secrets out of version control.
- Never move or rename vault files without explicit instruction.

## Useful Pointers

<!-- Shortcuts to non-obvious but important files or external systems. Examples:
- Bugs tracked in Linear project "BUGS".
- Oncall dashboard: grafana.internal/d/api-latency
-->
- Projects index: `30_Projects/_Projects.md`
- People index: `40_People/_PeopleIndex.md`
- Meeting index: `20_Meetings/_MeetingIndex.md`
- Skills reference: `90_System/Skills/`

## Known Pitfalls

<!-- Mistakes worth actively avoiding. Add a bullet when something goes wrong that
     was non-obvious and could happen again.
-->
- Record only mistakes worth actively avoiding next time.

## Topic memory (read only when relevant)
- `90_System/Memory/Routines_and_Sync.md`: day-start/day-end, mailbox, calendar and transcript sync, recovery commands.
- `90_System/Memory/Tools_and_Environment.md`: local tools, document formats, sandbox and environment quirks.

## Admission Rule
- Add a note only if it is reusable across future sessions, not already covered by `AGENTS.md` or `SOUL.md`, and worth its reading cost.
- Cross-task rules go here; topic- or tool-specific lessons go to the matching `90_System/Memory/<Topic>.md` (create a new topic file only when none fits, and list it above).
- No dated run logs or incident reports in memory; routine run results belong to the routine's own report.
