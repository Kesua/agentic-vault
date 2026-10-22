# Setup for AI agents

Instructions for an AI coding agent (Claude Code, Codex, Gemini CLI, OpenCode) that installs Agentic Vault for its owner. Goal: a working vault, history imported and daily routines ready, with the owner doing only what requires them: sign-ins, API tokens, answers to one batch of questions.

> **Owner:** open your agent in an empty folder or in this repository and paste:
>
> *Set up Agentic Vault for me by following SETUP_FOR_AGENTS.md from https://github.com/Kesua/agentic-vault. Ask me all questions at once.*

Human walkthrough of the same steps: [HOW_TO_INITIALIZE.md](HOW_TO_INITIALIZE.md).

## Rules for the agent

- **Never see secrets.** The owner enters tokens and OAuth files through the setup wizard or saves them into `90_System/secrets/` personally. Check files with existence tests only (`Test-Path`, `test -f`); never print, read, paste or commit their content. Never type a token or password for the owner.
- **Ask once.** Collect all decisions in step 2 in one message with the recommended defaults filled in, so the owner can answer "defaults" or change a few lines. Ask again only when a step fails.
- **Owner confirms outward actions.** Installing software, creating scheduled tasks and adding a git remote happen only after the owner approved them in step 2.
- **Long runs in the background.** Backfills can take from minutes to hours; run them in the background and keep going with other steps.
- **Report honestly.** Every step ends verified (command output, dry run, file exists) or listed as failed with the reason and the next action.

Paths below use Windows syntax. On macOS/Linux use `.venv/bin/python` and forward slashes.

## 1. Preflight (no questions yet)

1. If the repository is not cloned yet, clone it into the folder the owner named (default: `~/AgenticVault`):
   `git clone https://github.com/Kesua/agentic-vault.git <folder>`
2. Work from the repository root. Detect:
   - OS, and whether `winget` (Windows) or `brew` (macOS) exists.
   - Python 3.9+ (`python --version`, `py -3 --version`, `python3 --version`).
   - Which assistants are installed: `claude --version`, `codex --version`, `gemini --version`, `opencode --version`.
   - Whether Obsidian is installed (optional).
   - `git remote -v`: a fresh clone points `origin` at the **public** template.
3. Read `README.md`, `AGENTS.md`, `90_System/Automations/README.md` so you know the routines you will offer.

## 2. Ask the owner — one message

Send this as one message, with your recommendation pre-filled. Adapt the list to what preflight found.

| # | Question | Options | Recommended |
|---|---|---|---|
| 1 | Which services do you use? | Google Calendar, Gmail, Google Drive/Docs/Sheets/Slides, Todoist, Slack, Fireflies, Clockify, Telegram (phone notifications), daily news | Calendar + Gmail; add the others you use daily |
| 2 | One or two Google accounts? | `private` (work) only, or `private` + `personal` | One unless you really work from two |
| 3 | How far back to import? (per service) | 7 / 30 / 90 days / custom | Calendar 30, Gmail 14, Slack 7, Fireflies 30; Todoist 14 days ahead |
| 4 | Morning and afternoon routine times, timezone | any | Day start 05:30, day end 16:00, journal 16:30 on weekdays, local timezone |
| 5 | Extras in the routines | Focus topics + "Possibly forgotten" (always on), Telegram summary, commit to git | Telegram if connected; commit yes |
| 6 | Where does the vault's git history go? | Local only / your own **private** GitHub repo / none | Local only now; private remote later |
| 7 | Which scheduler runs the routines? | Codex app automations, Claude desktop scheduled tasks, OS scheduler (Task Scheduler/cron/launchd), none yet | Whichever assistant you use most, running locally |
| 8 | Project journals: start date for the first run | a date, or skip for now | 30 days back, once Gmail/Slack/Fireflies are imported |
| 9 | Language of summaries and notifications | e.g. English, Czech | Language you write most email in |
| 10 | Your name, role, and how you like answers | free text | Fills `SOUL.md`, `MEMORY.md`, `60_SOPs/_HowIWork.md` |
| 11 | Install missing tools? | Python, Obsidian, an assistant | Yes for Python; others only if wanted |

How long and how big the history import is (tell the owner when asking):
- Calendar: fast; one note per meeting.
- Gmail: daily summary per day plus one file per thread you replied to.
- Slack: slowest — a 30-day window with DMs can take an hour or more and create hundreds of files.
- Fireflies: one transcript section per recorded meeting; needs meeting notes from Calendar first for matching.
- Longer windows can be added later with the `bulk_*` skills; starting small is cheap.

## 3. Install

Run in the repository root. This is what `Setup_Windows.bat` / `Setup_Mac.command` do, minus the blocking wizard.

```powershell
python -m venv .venv                      # use the Python 3.9+ found in preflight
.\.venv\Scripts\python.exe -m pip install uv
.\.venv\Scripts\uv.exe sync --locked
New-Item -ItemType Directory -Force 90_System\secrets | Out-Null
```

- Missing Python on Windows: `winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements`; macOS: `brew install python@3.12` (only if approved in question 11).
- `uv sync` failing on Windows with build errors usually needs Visual Studio Build Tools; report it.
- Optional, if approved: browser automation `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\browser_playwright\install_playwright_browser_plugin.ps1` (macOS: `bash 90_System/Skills/browser_playwright/install_playwright_browser_plugin.sh`).
- If the owner chose "local only" or a private remote in question 6, rename the template remote so routines can never push to it: `git remote rename origin template`. For a private remote, after the owner confirms it is private: `git remote add origin <url>` and `git config --local agenticvault.pushUrl <url>`.

## 4. Connect accounts — the owner's part

Start the wizard in the background; it opens in the browser on the first free port 8470–8479:

```powershell
.\.venv\Scripts\python.exe -m src.wizard.server
```

Tell the owner exactly which wizard steps to complete (only the services chosen in question 1), and what each needs:

| Service | What the owner does | Result the agent checks (existence only) |
|---|---|---|
| Google (Calendar, Gmail, Drive) | Create one Google Cloud **Desktop app** OAuth client with the needed APIs enabled ([guide](HOW_TO_INITIALIZE.md#google-calendar-setup)), upload its JSON in the wizard, click sign-in per service and account | `gcal_token_<account>.json`, `gmail_token_<account>.json`, `gdrive_token_<account>.json` |
| Todoist | Paste the API token from Todoist settings → Integrations → Developer | `todoist_token_personal.json` |
| Slack | Create a Slack app from `90_System/Integrations/slack/app_manifest.readonly.yaml`, install it, paste the **User OAuth Token**, pick workspace exclusions | `slack_user_token_<alias>.txt`, `90_System/Integrations/slack/workspaces.json` |
| Fireflies | Paste the API key from Fireflies settings | `fireflies_api_key.txt` |
| Clockify | Paste the API key from profile settings | `clockify_token.txt` |
| Telegram | Create a bot with @BotFather, paste the token, send the bot a message, let the wizard detect IDs | `telegram_bridge.env` |

Files live in `90_System/secrets/`. Track progress without reading secrets:

```powershell
Invoke-RestMethod http://localhost:8470/api/health   # flags like gcal_private_authed, slack_connected (adjust the port)
```

Google sign-in can also be started from the terminal; the owner only clicks Allow in the browser:
`.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py auth --account private`
(Gmail: `90_System\Skills\gmail_assistant\gmail_assistant.py auth --account private`; Drive: `90_System\Skills\google_drive_assistant\google_drive_assistant.py auth --account private`.)

Stop the wizard when done: `Invoke-RestMethod -Method Post http://localhost:8470/api/shutdown`.

## 5. Verify each connected service

Run a dry run per connected service; fix or report failures before importing.

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync --dry-run
.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync --dry-run
.\.venv\Scripts\python.exe 90_System\Skills\daily_brief_todoist\daily_brief_todoist.py sync --dry-run
.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --dry-run
.\.venv\Scripts\python.exe 90_System\Integrations\telegram_bridge\send_telegram_notification.py --html "<b>Agentic Vault</b> test" --dry-run
```

For Slack, use the wizard's "Test connection" or `GET /api/slack/list-conversations`. `invalid_grant` from Google means: run the `auth` command again.

## 6. Import history

Use the windows from question 3, in this order (later steps link to earlier results). Run long ones in the background.

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py sync --days-back 30 --accounts private
.\.venv\Scripts\python.exe 90_System\Skills\process_emails\process_emails.py sync --days-back 14 --accounts private
.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --days-back 7 --include-dm --include-mpim
.\.venv\Scripts\python.exe 90_System\Skills\fireflies_sync\fireflies_sync.py sync --days-back 30
.\.venv\Scripts\python.exe 90_System\Skills\daily_brief_todoist\daily_brief_todoist.py sync --days-ahead 14
.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync
.\.venv\Scripts\python.exe 90_System\Skills\create_links\create_links.py sync
```

- Skip lines for services not connected; add `personal` to `--accounts` when both Google accounts are used.
- Then run the `regular_day_start` skill once, so today's brief exists with news and focus topics.
- If question 8 has a date, run `regular_project_journal` once for that window, following `90_System/Skills/project_journal/RUNBOOK.md`.

## 7. Personalize

From the answers to questions 9–10, edit only placeholder content in:
- `SOUL.md` — tone and language.
- `MEMORY.md` — preferences (language, answer length); keep it short.
- `60_SOPs/_HowIWork.md` — priorities, meeting style.

Mention to the owner: open the folder as a vault in Obsidian.

## 8. Schedule the routines

Use the prompts in `90_System/Automations/` (`DayStart.md`, `DayEnd.md`, `ProjectJournal.md`). Keep or delete their optional lines according to question 5, add the language from question 9, and put times only in the scheduler.

Schedule only **local** runs: the routines need the local `.venv` and `90_System/secrets/`. Cloud runs (for example Claude Code `/schedule` routines) cannot reach them.

| Scheduler (question 7) | How |
|---|---|
| Codex app | Give the owner the prompts; they add them under Automations with this folder as the project and the chosen times. |
| Claude desktop app | Create local scheduled tasks with the prompts and this folder, if your tools allow it; otherwise give the owner the prompts. |
| OS scheduler | Create a daily task that starts the assistant headless in this folder, e.g. `codex exec "<prompt>"` or `claude -p "<prompt>"`. Make sure its permission settings allow the skill commands, then trigger it once to test. |

If the owner chose "none yet", leave the prompts and say the vault updates only when asked.

## 9. Final report to the owner

Finish with one short checklist:
- Connected services and their dry-run result.
- Imported windows and counts (meeting notes, mailbox days, transcripts, people notes).
- Scheduled routines and times, or the prompts still to paste.
- Git state: remotes, whether pushing is enabled.
- Anything the owner still has to do (for example: add yourself as a Google test user, re-run sign-in).
- How to start: open the vault in Obsidian, open the assistant in this folder, ask *"What should I focus on today?"*
