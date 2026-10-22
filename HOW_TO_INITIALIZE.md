# HOW TO INITIALIZE

This file is for a new, non-technical user of this vault.

If you already use Claude Code or Codex, you can let it do most of this for you: see [SETUP_FOR_AGENTS.md](SETUP_FOR_AGENTS.md).

Goal:
- get the vault open
- put every secret in the right place
- connect the outside services this vault knows how to use
- schedule the skills you want to keep your notes current
- avoid putting passwords or tokens into the wrong files

## What a skill is

In this vault, a `skill` is a small helper tool with one clear job.

Examples:

- read your Google Calendar and create meeting notes
- read Gmail and summarize threads
- read Todoist and place tasks into Daily Briefs
- read Fireflies and attach transcript summaries to meetings
- open a real browser session for web pages that block simple fetch tools

You can think of a skill as a safe connector between this vault and one outside service.

## How skills help Claude or Codex

Claude or Codex does not just “magically know” your calendar, email, Slack, or tasks.

Instead, it uses these skills to access them in a controlled way.

That matters because:

- each skill knows exactly where to read and write in the vault
- each skill knows which secret file to use
- each skill limits what the agent can do
- each skill makes the automation repeatable and safer

Without the skill, the agent should not improvise direct access to those outside services.

## Why correct setup matters

If a skill is set up correctly:

- the vault can pull the right data
- the right account is used
- your notes stay organized
- secrets stay private
- the agent can help you reliably

If a skill is set up badly:

- the wrong Google account may connect
- a token may be saved in the wrong place
- an automation may fail
- Slack or Gmail may not open at all
- the agent may not be allowed to help with that service

So the setup is important because it is the foundation that makes the rest of the vault useful.

## What skills are there?
Some skills work with no account setup.
Some skills need you to connect your own accounts first.

The important skill groups in `90_System/Skills/` are:

- `gcal_today` and `adhoc_gcal`
  - Google Calendar
- `gmail_assistant` and `process_emails`
  - Gmail
- `google_drive_assistant`
  - Google Drive, Docs, Sheets, and Slides
- `daily_brief_todoist` and `adhoc_todoist`
  - Todoist
- `fireflies_sync` and `adhoc_fireflies`
  - Fireflies
- `slack_assistant` and `process_slack`
  - Slack
- `clockify_sync`
  - Clockify
- `Web_Daily_Brief`
  - daily news and weather
- `create_links`, `files_search`, `deferred_task_queue`, `meeting_attendees_people_sync`, `git_submodules_pull`
  - internal vault helpers
- `browser_playwright`
  - optional real-browser automation for browser-gated websites and screenshots

## Before you start

You do not need to understand technical words like:

- `OAuth`
  - this just means “Google opens a safe sign-in window and asks if this vault may access your account”
- `API token` or `API key`
  - this is just a secret pass used by the vault to talk to a service on your behalf

## Very important safety rule

All secrets belong only in:

- `90_System/secrets/`

Never paste tokens into:

- markdown notes
- screenshots
- chat messages
- Slack config text
- `app_info.txt`
- Git commits

## Quick start (recommended)

The fastest way to set up is the automated setup wizard.

- **Windows:** double-click `Setup_Windows.bat` in the vault folder
- **Mac:** double-click `Setup_Mac.command` in the vault folder

The script installs Python if needed, creates the virtual environment, installs
dependencies, and opens a browser-based wizard that walks you through connecting
each service.

The wizard can run one initial import. **That import runs once.** To keep notes
current, schedule a connected `regular_*` skill as a recurring task in Codex,
Claude Code, or another assistant that supports routines. The wizard does not
create a schedule for you.

It also checks whether Claude Code, OpenAI Codex, Gemini CLI, or OpenCode is
already installed on Windows or macOS. If none is available, the wizard lets you
choose which coding assistant to install. The wizard can also:

- configure Google Workspace (Calendar, Gmail, Drive, Docs, Sheets, and Slides)
- set up a local AI model via LM Studio or Ollama with optional OpenCode integration
- install optional Playwright browser tooling for browser-first web tasks

> **Mac note (ZIP downloads):** if macOS says "permission denied" when you
> double-click `Setup_Mac.command`, open Terminal once and run:
>
> ```bash
> chmod +x Setup_Mac.command _setup/bootstrap_mac.sh
> ```
>
> Then double-click again. This is only needed when the vault was downloaded as
> a ZIP rather than cloned with Git.

If you prefer to set things up manually, continue with the steps below.

---

## Step 1: Install the two apps you need

Please install:

- Obsidian
  - use it to open and read the vault
- Python from `python.org`
  - during installation, tick the box that says `Add Python to PATH`

If someone technical is helping you, they should then open PowerShell in this folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install uv
.\.venv\Scripts\uv.exe sync --locked
```

## Step 2: Open the vault

Do this:

1. Open Obsidian.
2. Choose `Open folder as vault`.
3. Select this repository folder.

## Step 3: Create the secrets folder

If it does not already exist, create:

- `90_System/secrets/`

This folder is already ignored by Git, which means your secrets should stay local on your computer.

## Step 4: Decide which services you actually want

You do not need every connection on day one.

Recommended order:

1. Google Calendar
2. Gmail
3. Google Drive / Docs / Sheets / Slides
4. Todoist
5. Fireflies
6. Slack
7. Clockify
8. Telegram bridge
9. Local AI (LM Studio or Ollama)
10. Playwright browser tooling (optional)

If you skip one service, only that skill stays unavailable. The rest of the vault can still work.

---

## Google Calendar setup

Used by:

- `90_System/Skills/gcal_today/`
- `90_System/Skills/adhoc_gcal/`

What it gives you:

- meeting notes created from your calendar
- meeting backfill
- optional meeting creation drafts

### What you need

- a Google account
- if you use two accounts, treat them as:
  - `private` = work/private Google account
  - `personal` = personal Google account

### What you will create

- one Google Cloud project
- Google Calendar API switched on
- one Desktop App sign-in file

### Easy version

The easiest setup is:

1. Create one Google Cloud project.
2. Turn on both:
   - Google Calendar API
   - Gmail API
   - Google Drive, Docs, Sheets, and Slides APIs if you want editing skills
3. Create one Desktop App OAuth client.
4. Download the JSON file once.
5. Save a copy of that same file in this vault under the names this repo expects.

### Where to click in Google

Based on Google’s official quickstart documentation:

1. Open Google Cloud Console.
2. Create a project, or choose an existing one.
3. Turn on `Google Calendar API`.
4. Go to `Google Auth platform`.
5. If Google says setup has not started yet, click `Get Started`.
6. Fill in the basic app details:
   - app name
   - support email
   - contact email
7. In `Audience`, if Google asks, add yourself as a test user if the app is not public.
8. Go to `Clients`.
9. Click `Create Client`.
10. Choose `Desktop app`.
11. Give it any name you like.
12. Download the JSON file.

### Where to place the file in this vault

Simplest choice:

- save a copy as `90_System/secrets/gcal_oauth_client.json`

If you want separate Google sign-in files for each account, use:

- `90_System/secrets/gcal_oauth_client_private.json`
- `90_System/secrets/gcal_oauth_client_personal.json`

### What happens next

When you sign in for the first time, the vault will create these files automatically:

- `90_System/secrets/gcal_token_private.json`
- `90_System/secrets/gcal_token_personal.json`

If you later want the vault to create calendar events, it may also create:

- `90_System/secrets/gcal_adhoc_token_private.json`
- `90_System/secrets/gcal_adhoc_token_personal.json`

### First sign-in

If someone is helping you run the setup, these are the commands:

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py auth --account private
.\.venv\Scripts\python.exe 90_System\Skills\gcal_today\gcal_today.py auth --account personal
```

Google will open a browser window.

You should:

- choose the correct Google account
- click `Allow`

### If the wrong Google account was connected

Delete only the matching token file:

- `gcal_token_private.json` or `gcal_token_personal.json`

Then sign in again.

---

## Gmail setup

Used by:

- `90_System/Skills/gmail_assistant/`
- `90_System/Skills/process_emails/`

What it gives you:

- email search
- thread summaries
- attachment downloads
- draft replies
- mailbox exports into the vault

### Good news

You can usually reuse the same Google Cloud project and the same downloaded Desktop App JSON from the Google Calendar setup above.

### What Google needs

Based on Google’s official Gmail quickstart:

1. In the same Google Cloud project, turn on `Gmail API`.
2. Keep the same Google Auth setup.
3. Use a Desktop App OAuth client.

### Where to place the file in this vault

Simplest choice:

- save a copy as `90_System/secrets/gmail_oauth_client.json`

If you want separate files per account, use:

- `90_System/secrets/gmail_oauth_client_private.json`
- `90_System/secrets/gmail_oauth_client_personal.json`

### What happens next

When you sign in for the first time, the vault will create:

- `90_System/secrets/gmail_token_private.json`
- `90_System/secrets/gmail_token_personal.json`

### First sign-in

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py auth --account private
.\.venv\Scripts\python.exe 90_System\Skills\gmail_assistant\gmail_assistant.py auth --account personal
```

### Important tip

Before signing in:

- open the correct Google account in your browser
- or use separate browser profiles for work and personal

That avoids connecting the wrong inbox.

---

## Google Drive / Docs / Sheets / Slides setup

Used by:

- `90_System/Skills/google_drive_assistant/`

What it gives you:

- search and browse files across your Google Drive
- read and export Google Docs, Sheets, and Slides
- edit and update documents from inside the vault

### Good news

If you already set up Google Calendar or Gmail, you can reuse the same Google Cloud project and the same Desktop App OAuth JSON file.

### What Google needs

Based on Google's official API quickstart documentation:

1. In the same Google Cloud project, turn on:
   - Google Drive API
   - Google Docs API
   - Google Sheets API
   - Google Slides API
2. Keep the same Google Auth setup.
3. Use a Desktop App OAuth client.

### Where to place the file in this vault

Simplest choice:

- save a copy as `90_System/secrets/gdrive_oauth_client.json`

If you want separate files per account, use:

- `90_System/secrets/gdrive_oauth_client_private.json`
- `90_System/secrets/gdrive_oauth_client_personal.json`

### What happens next

When you sign in for the first time, the vault will create:

- `90_System/secrets/gdrive_token_private.json`
- `90_System/secrets/gdrive_token_personal.json`

### First sign-in

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py auth --account private
.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py auth --account personal
```

Google will open a browser window. Choose the correct account and click `Allow`.

---

## Todoist setup

Used by:

- `90_System/Skills/daily_brief_todoist/`
- `90_System/Skills/adhoc_todoist/`

What it gives you:

- tasks written into Daily Briefs
- task search
- optional task creation

### What you need

- your personal Todoist API token

### Where Todoist says to find it

According to Todoist’s official API documentation, your personal API token is in your account’s integration settings.

### Simple steps

1. Open Todoist in your browser.
2. Open your account settings.
3. Go to `Integrations`.
4. Find your personal API token.
5. Copy it.

### Where to save it

Create this file:

- `90_System/secrets/todoist_token_personal.json`

Put this inside:

```json
{"token":"PASTE_YOUR_TODOIST_TOKEN_HERE"}
```

### That is enough

Nothing else is needed for Todoist.

---

## Fireflies setup

Used by:

- `90_System/Skills/fireflies_sync/`
- `90_System/Skills/adhoc_fireflies/`

What it gives you:

- transcript summaries attached to meeting notes
- search across transcripts

### What you need

- a Fireflies API key

### Where Fireflies says to find it

According to Fireflies official docs:

1. Log in to Fireflies.
2. Open `Integrations`.
3. Open `Fireflies API`.
4. Copy your API key.

Some Fireflies pages also describe this as `Settings` or `Developer Settings`. If the menu labels differ slightly, look for the area about API access and copy the key shown there.

### Where to save it

Create this file:

- `90_System/secrets/fireflies_api_key.txt`

The file should contain only the key.

No extra words.
No quotes.
No JSON.

### Optional advanced preference

You can stop here.

There are a few optional Fireflies preferences using environment variables, but most people do not need them.

---

## Slack setup

The vault reads Slack with a **User OAuth Token**. It discovers conversations visible to that user. The regular routine includes direct and group messages; add conversation IDs to the exclusion list when they must stay out of the vault.

1. Create and install a Slack app from `90_System/Integrations/slack/app_manifest.readonly.yaml`. A workspace administrator may need to approve its user read scopes.
2. Copy the **User OAuth Token** into `90_System/secrets/slack_user_token_private.txt`. Keep it out of notes and Git.
3. Copy `90_System/Integrations/slack/workspaces.example.json` to the ignored `90_System/Integrations/slack/workspaces.json` and fill in the workspace ID and your own Slack user ID. Leave `exclude_conversation_ids` empty to include all visible conversations, or list IDs to skip.
4. Run `slack_assistant.py auth-check --workspace private`, then `process_slack.py sync --workspace private --dry-run --include-dm --include-mpim` before the first real sync.

The setup wizard performs steps 2 and 3 after the app is installed. It can list conversations so you can mark exclusions. A previous bot-token `token_file` / `allow_conversations` config must be replaced for user-token reads. See `90_System/Integrations/Documentation/slack_setup.md` for the full commands and data boundaries.

---
## Clockify setup

Used by:

- `90_System/Skills/clockify_sync/`

What it gives you:

- list projects
- list time entries
- summarize time
- create time entries

### What you need

- one Clockify API key

### Where Clockify says to find it

According to Clockify’s official help:

1. Open Clockify.
2. Open your profile or preferences.
3. Go to the `Advanced` tab.
4. Click `Manage API keys`.
5. Click `Generate new`.
6. Give the key a name.
7. Click `Generate`.
8. Copy it immediately.

Clockify warns that you may not be able to see the full key again later, so save it right away.

### Where to save it

Create this file:

- `90_System/secrets/clockify_token.txt`

Put only the key inside.

### Important warning

Clockify says API keys follow the same permissions as your normal Clockify account.

That means this key is powerful.

Store it carefully.

---

## Telegram bridge setup

Used by:

- `90_System/Integrations/telegram_bridge/`

What it gives you:

- send a text message to a Telegram bot
- have that bot ask your configured coding assistant to work inside this vault

### You can skip this

This is optional.

Only set this up if you really want to talk to the vault from Telegram.

### What you need

- a Telegram bot token from `@BotFather`
- your own Telegram user ID
- your own Telegram chat ID

### Step A: create the bot

According to Telegram’s official bot docs:

1. Open Telegram.
2. Search for `@BotFather`.
3. Start a chat.
4. Send `/newbot`.
5. Pick a bot name.
6. Pick a username that ends with `bot`.
7. Copy the token BotFather gives you.

### Step B: create the local config file

Create this file:

- `90_System/secrets/telegram_bridge.env`

Put this inside:

```env
TELEGRAM_BOT_TOKEN=PASTE_YOUR_BOT_TOKEN_HERE
TELEGRAM_ALLOWED_USER_IDS=PUT_YOUR_TELEGRAM_USER_ID_HERE
TELEGRAM_ALLOWED_CHAT_IDS=PUT_YOUR_TELEGRAM_CHAT_ID_HERE
```

Optional extra lines if you need them:

```env
AGENT_COMMAND=codex
BRIDGE_ACCEPT_PLAIN_TEXT=true
```

### About `VAULT_ROOT`

You usually do not need to set `VAULT_ROOT`.

The current bridge code already defaults to this repository folder automatically.

### Step C: find your Telegram IDs

Simple method:

1. Start a chat with your new bot.
2. Send `/start`.
3. Run the bridge once.
4. Look at the bridge logs.
5. Copy the `user_id` and `chat_id` shown there into the env file above.

### Security rule

Only allow your own IDs, or people you fully trust.

---

## Web Daily Brief setup

Used by:

- `90_System/Skills/Web_Daily_Brief/`

What it gives you:

- weather
- events
- trends
- market snapshot

### What you need

- nothing personal

There is no personal token to place for this one.

It uses fixed public sources through the repo’s own script.

---

## Skills that need little or no account setup

These can usually work once Python is installed:

- `create_links`
- `files_search`
- `deferred_task_queue`
- `meeting_attendees_people_sync`
- `git_submodules_pull`

`process_emails`, `process_slack`, `adhoc_gcal`, `adhoc_fireflies`, and `adhoc_todoist` do not need separate setup if their parent service above is already connected.

---

## Your finished secrets checklist

When you are done, your `90_System/secrets/` folder may contain some or all of these:

- `gcal_oauth_client.json`
- `gcal_oauth_client_private.json`
- `gcal_oauth_client_personal.json`
- `gcal_token_private.json`
- `gcal_token_personal.json`
- `gcal_adhoc_token_private.json`
- `gcal_adhoc_token_personal.json`
- `gmail_oauth_client.json`
- `gmail_oauth_client_private.json`
- `gmail_oauth_client_personal.json`
- `gmail_token_private.json`
- `gmail_token_personal.json`
- `gdrive_oauth_client.json`
- `gdrive_oauth_client_private.json`
- `gdrive_oauth_client_personal.json`
- `gdrive_token_private.json`
- `gdrive_token_personal.json`
- `todoist_token_personal.json`
- `fireflies_api_key.txt`
- `slack_user_token_private.txt`
- `slack_user_token_personal.txt`
- `clockify_token.txt`
- `telegram_bridge.env`

You will probably not need all of them.

That is normal.

---

## Local AI setup (optional)

What it gives you:

- run a language model entirely on your own computer
- no cloud API key needed
- works with OpenCode through a local model alias

### What you need

- LM Studio or Ollama installed on your machine

### Easy way: use the wizard

The setup wizard handles this automatically.

During setup, select the `Local AI` step. The wizard will:

1. Detect whether LM Studio or Ollama is already installed.
2. If not installed, offer to download and install it for you.
3. Let you choose a model (for example Gemma 3).
4. Configure OpenCode to use that model with the alias `gemma-local`.

### Manual way

If you prefer to set this up by hand:

1. Install LM Studio from `https://lmstudio.ai` or Ollama from `https://ollama.com`.
2. Download a model and start the local server.
3. LM Studio runs by default at `http://127.0.0.1:1234/v1`.
4. In your `opencode.json`, add a provider entry pointing to that URL.

### Security note

After a model is downloaded, local inference can run without sending prompts to a cloud model. Downloading a model and any other connected vault skills still use the network.

---

## Best first-day setup plan

If you want the simplest possible start, do only this:

1. Double-click `Setup_Windows.bat` or `Setup_Mac.command`.
2. In the wizard, set up Google Calendar and Gmail.
3. Set up Todoist.
4. Stop there.

That already unlocks a large part of the vault.

Later, add:

5. Google Drive / Docs / Sheets / Slides
6. Fireflies
7. Slack
8. Clockify
9. Local AI (if you want to run models offline)
10. Telegram bridge

---

## Make notes update automatically

1. Connect the service in the wizard. Run its optional initial load to create the first notes.
2. Ask your coding assistant to run the matching `regular_*` skill once in this vault. Check the notes it created.
3. In an assistant that supports recurring tasks, schedule that same skill at a time you choose. If it does not support recurring tasks, use a scheduler that starts the assistant in this vault.

| Connected service | Skill to schedule | Result |
|---|---|---|
| Google Calendar | `regular_gcal_today` | Upcoming meetings appear under `20_Meetings/`. |
| Gmail | `regular_process_emails` | Important email context appears under `00_Mailbox/`. |
| Todoist | `regular_daily_brief_todoist` | Tasks refresh in upcoming daily briefs. |
| Slack | `regular_process_slack` | Visible conversations appear under `00_Mailbox/`. |
| Fireflies | `regular_fireflies_sync` | Transcript summaries attach to meeting notes. |

Example request in your assistant: “In this vault, schedule the repo-local `regular_gcal_today` skill every weekday at 08:00 in my local timezone. Run it once now, and tell me if a run fails.” Change the skill and time to match what you connected. The `regular_day_start` and `regular_day_end` wrappers run several skills; use them only after connecting the services listed in their skill files.

**The wizard does not create a recurring task.** If you do not schedule a skill, use it on demand; notes will not keep syncing in the background.

---

## Project journals (optional)

Use `regular_project_journal` in Codex or `regular-project-journal` in Claude Code for scheduled or explicitly requested incremental project history. Start with `30_Projects/Journal/_Journal.md`; new journals use `30_Projects/Templates/ProjectJournal_TEMPLATE.md`.

1. Choose the configured Gmail, Slack and Fireflies sources to cover, your timezone and the first date window to inspect. Missing services stay unavailable; the workflow does not need additional credentials.
2. Ask the assistant to run the journal skill once for that window. Check its source links and the resulting commitments. No material change means no journal edit.
3. If you want daily updates, schedule the assistant to run this skill at a time you choose, preferably after relevant exports. Installing the skill does not create a recurring task.

Keep one stable file per project. Each entry records only a new commitment, decision, dependency or evidenced completion; repeated runs preserve history and avoid duplicates. Collection and retry details: `90_System/Skills/project_journal/RUNBOOK.md`.

## If something goes wrong

Most connection problems come from one of these:

- the secret file is in the wrong folder
- the file name is slightly wrong
- the wrong Google account was chosen in the browser
- a company admin blocked the app
- the token was pasted with extra spaces

When in doubt:

1. Check the file name carefully.
2. Check that the file is inside `90_System/secrets/`.
3. Re-copy the token.
4. Re-run the sign-in step for that service only.

---

## Official references used for this guide

- Google Calendar API quickstart:
  - https://developers.google.com/workspace/calendar/api/quickstart/python
- Gmail API quickstart:
  - https://developers.google.com/workspace/gmail/api/quickstart/python
- Slack app install and OAuth:
  - https://api.slack.com/authentication/oauth-v2
  - https://api.slack.com/authentication/quickstart
- Todoist API:
  - https://developer.todoist.com/api/v1/
- Fireflies API authorization:
  - https://docs.fireflies.ai/fundamentals/authorization
- Telegram bot creation:
  - https://core.telegram.org/bots/features
- Clockify API key help:
  - https://clockify.me/help/getting-started/manage-your-profile-settings
  - https://clockify.me/help/administration/api-webhook-settings
