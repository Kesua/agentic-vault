# Automations

Ready-to-paste prompts for scheduled runs. The setup wizard does not schedule anything: copy a prompt into your assistant's scheduler, point it at this vault folder, and pick a time.

| Prompt | Suggested schedule | What you get |
|---|---|---|
| [Day start](DayStart.md) | Every day 05:30 | Fresh meeting notes, tasks, mailbox and news, plus **Focus topics for today** in the brief |
| [Day end](DayEnd.md) | Every day 16:00 | Transcripts, people and links updated, plus **Possibly forgotten** replies and promises |
| [Project journal](ProjectJournal.md) | Weekdays 16:30 | New decisions, deadlines and handoffs in one journal per project |

## Where to paste
- **Codex app** — Automations → New automation → paste the prompt, choose this vault as the project, set the schedule.
- **Claude Code** — create a scheduled task (desktop app or `/schedule`) that runs in this vault with the prompt.
- **Other assistants or no scheduler** — any OS scheduler (Task Scheduler, cron, launchd) that starts your assistant non-interactively in this folder with the prompt.

## Optional lines
Each prompt has optional lines. Delete them or keep them:

- **Telegram** — needs the wizard's Telegram step; sends a short summary to your single allow-listed chat.
- **Commit** — commits only routine-owned folders with `routine: <name> <date>`.
- **Push** — needs a one-time private-remote setup (see `.agents/skills/regular_vault_commit/SKILL.md`). Never push the vault to a public repository.
- **Language** — add a line such as `Write the focus topics and Telegram messages in Czech.`

## Keep the schedule and the prompt in sync
Put times only in the scheduler, not in the prompt text, so the two cannot disagree.
