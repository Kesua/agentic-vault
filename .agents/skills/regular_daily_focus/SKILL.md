---
name: "regular_daily_focus"
description: "Morning routine step: suggest today's focus topics from yesterday's stored email and Slack plus today's meetings and tasks, and write them into today's Daily Brief."
---

# Regular Daily Focus

Turn yesterday's conversations into a short list of what deserves attention today. Runs at the end of `regular_day_start`, after the mailbox, calendar and Todoist syncs.

## Inputs (local files only)
- Yesterday's mailbox exports in `00_Mailbox/YYYY/MM/DD/`: `emails_summary.md`, `slack_summary.md` and the thread snapshots in the same folder.
- Today's meeting notes in `20_Meetings/YYYY/MM/DD/`.
- The `# Tasks` section of today's brief `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`.
- Relevant project journals in `30_Projects/Journal/` only when a topic clearly belongs to one; read its open commitments, not its history.

Do not query Gmail, Slack or any other service. If yesterday's exports are missing, use the latest earlier day that exists and say which day was used.

## Output
Replace only the `# Focus topics for today` section of today's brief, creating it after `# Tasks` if missing. Preserve every other section.

```markdown
# Focus topics for today
- **Acme renewal** — revised quote requested yesterday; call at 14:00. [Slack](../../../00_Mailbox/2026/10/21/slack_acme_renewal_1729.md)
- **Q4 budget** — finance waits for your comments, due tomorrow. [Email](../../../00_Mailbox/2026/10/21/18f2_q4-budget.md)
```

- 3 to 7 topics, most important first. One line each: bold topic, why it matters today, one source link.
- Prefer commitments, deadlines, questions addressed to the owner, and anything linked to today's meetings.
- Skip newsletters, automated alerts, invitations without a question, and threads already answered.
- Without anything worth attention, write one bullet: `- Nothing urgent from yesterday's messages.`

## Report
Return the topic list as plain text so the caller can reuse it, for example in a Telegram summary.
