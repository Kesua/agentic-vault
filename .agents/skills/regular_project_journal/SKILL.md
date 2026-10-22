---
name: regular_project_journal
description: Use when a scheduled run maintains project journals, or the vault owner explicitly requests the same incremental journal update.
---

# Incremental project journals

Keep one stable file per project in `30_Projects/Journal/<Project>.md`, with the shared index `_Journal.md`. Use the owner's configured accounts and timezone. Scheduling is a separate setup step; installing this skill does not schedule or run it.

## Workflow

1. Read `90_System/Integrations/project_journal/runtime/state.json` if it exists. Follow `90_System/Skills/project_journal/RUNBOOK.md` for source collection and progress tracking.
2. Check new information through the existing dedicated Gmail, Slack and Fireflies skills, with Calendar only where needed. Continue from each source's last successful period with a 72-hour overlap; keep missing or late transcripts pending. A summary is not a full transcript, and an invitation is not proof of attendance.
3. List files and search first. For each affected project, read relevant open commitments and the latest two daily entries; retrieve older context only to resolve a specific question. Do not load all journals or the full index.
4. Compare meaning: a new commitment, changed owner or deadline, evidenced completion, new dependency, or decision that changes the next action. Repeated waiting, formatting and another link to the same fact are not changes.
5. Add new bullets under `### YYYY-MM-DD` in `## Daily entries`, newest day first. Extend an existing day instead of duplicating the date or event. Put late evidence under its original event date with `added YYYY-MM-DD`. Label corrections and preserve the earlier decision.
6. Update open commitments, short status and index rows only when their meaning changes. Preserve manual text and history. Without a material change, write nothing.

## Entry format

One bullet is one action or change, one sentence, at most **25 words excluding its single source link**. Usually 1–3 bullets per project per day; do not drop independent commitments to meet that typical count.

```markdown
### 2026-10-21
- Done — draft approved; Petra to publish by 2026-10-23. [Client email](../../00_Mailbox/2026/10/21/approved-thread.md)
```

Use `Task — owner: action; agreed deadline`, `Done — evidenced result`, `Waiting — dependency` or `Change — decision`. Include only agreed deadlines. Sent does not mean accepted; proposed does not mean approved. Use an actual verified source rather than the example link.

## New projects and boundaries

- Create a journal only for evidenced work or an accepted commitment by the owner. Check names and aliases; one company can have multiple projects. Keep unclear mentions in runtime state.
- Add a new or renamed journal to `30_Projects/Journal/_project_map.json` (client domains, meeting title keywords, dedicated Slack channels); meeting notes get their `project:` from it.
- Start from `30_Projects/Templates/ProjectJournal_TEMPLATE.md`: title, one scope sentence and the first meaningful entry. Add its link/status to `_Journal.md` and link the journal from `30_Projects/_Projects.md`. Do not copy historical reconstructions or create empty daily entries.
- Keep source inventories, transcript quotations, repeated summaries, unchanged tasks and operational errors out of journals. Errors belong in runtime state.
- Check dates, sources, brevity and semantic duplicates before confirming source progress. Leave incomplete sources pending for retry. Report only change counts and required action; stay quiet when nothing changed.
- This skill permits journal maintenance only. It does not authorize sending messages, changing external tasks, committing, pushing or creating a recurring schedule.
