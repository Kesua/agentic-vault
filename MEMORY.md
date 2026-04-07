# MEMORY

This file is read at the start of every agent session. Use it to record preferences,
rules, and pointers that should persist across conversations. Keep entries short and
operational. Delete or replace the placeholder lines below with your own.

---

## Preferences

<!-- How you want the agent to communicate and behave by default. Examples:
- Always reply in English.
- Keep responses to three bullets or fewer.
- Never use emojis.
-->
- Keep bullets short and operational.

## Learned Rules

<!-- Durable lessons from past sessions — things the agent should always remember.
     Add a new bullet any time you correct the agent or it makes a mistake worth
     avoiding again. Remove rules that are no longer relevant.
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
