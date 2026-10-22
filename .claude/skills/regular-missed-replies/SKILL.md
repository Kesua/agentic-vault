---
name: "regular-missed-replies"
description: "Evening routine step: check today's stored email and Slack for replies or promised actions the owner may have forgotten, and write them into today's Daily Brief."
---

# Regular Missed Replies

This is a Claude Code mirror of `regular_missed_replies` from `.agents/skills/`.
Original source: `.agents/skills/regular_missed_replies/SKILL.md`
Skill class: `regular`

Catch what slipped through before the day ends. Runs at the end of `regular_day_end`, after the mailbox and Fireflies syncs.

## Inputs (local files only)
- Today's mailbox exports in `00_Mailbox/YYYY/MM/DD/`: `emails_summary.md`, `slack_summary.md` and the thread snapshots in the same folder.
- Today's meeting notes in `20_Meetings/YYYY/MM/DD/`, especially action items in `## Fireflies (auto)` owned by the vault owner.
- Today's brief `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`, so items already listed as tasks or focus topics are not repeated.

Do not query Gmail, Slack or any other service, and do not draft or send replies.

## What counts
- A question or request addressed to the owner with no later reply from the owner in the stored thread.
- Something the owner promised today ("I'll send…", "will check…") with no evidence it was done.
- A meeting action item owned by the owner and due within two days.

Skip automated messages, newsletters, invitations, requests directed to someone else, and threads where the owner already replied last.

## Output
Replace only the `# Possibly forgotten` section of today's brief, creating it at the end if missing. Preserve every other section.

```markdown
# Possibly forgotten
- **Reply to Petra** — asked for the signed NDA at 11:20, no answer yet. [Email](../../../00_Mailbox/2026/10/22/18f9_nda.md)
- **Send the demo recording** — promised in the 14:00 call. [[1400 - Acme renewal call]]
```

- At most 7 items, most time-sensitive first. One line each with one source link.
- Without findings, write one bullet: `- Nothing obviously forgotten today.`

## Report
Return the list as plain text so the caller can reuse it, for example in a Telegram reminder.
