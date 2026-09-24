param(
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$Destination,
    [switch]$PreserveExisting = $true
)

$ErrorActionPreference = "Stop"

$sourceRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Ensure-Directory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Write-Utf8File {
    param(
        [string]$Path,
        [string]$Content
    )
    $parent = Split-Path -Parent $Path
    if ($parent) {
        Ensure-Directory -Path $parent
    }
    if ($PreserveExisting -and (Test-Path -LiteralPath $Path)) {
        return
    }
    if (Test-CredentialText -Content $Content) {
        Write-Warning "Skipped content containing a credential: $Path"
        return
    }
    Set-Content -LiteralPath $Path -Value $Content -Encoding utf8
}

function Test-ExcludedExportPath {
    param([string]$RelativePath)

    $normalized = $RelativePath.Replace('/', '\').TrimStart('\')
    $segments = $normalized -split '\\'
    foreach ($segment in $segments) {
        if (@('secrets', 'runtime', 'logs', '__pycache__', '.venv') -contains $segment.ToLowerInvariant()) {
            return $true
        }
    }

    $fileName = $segments[-1].ToLowerInvariant()
    if ($fileName -match '^\.env($|[._-])|(^|[._-])(credential|credentials|token|tokens|secret|secrets|password|oauth_client|private_key)([._-]|$)|^app_info\.txt$|^id_rsa($|\.)|\.(pem|key|p12|pfx|jks)$') {
        return $true
    }
    if ($normalized -ieq '90_System\Integrations\slack\workspaces.json') {
        return $true
    }
    $ownerSpecificPrefixes = @(
        '.agents\skills\adhoc_client_meeting_summary\',
        '.agents\skills\adhoc_dph_invoicing\',
        '.agents\skills\adhoc_smartscout_db\',
        '.agents\skills\investment_',
        '.claude\skills\adhoc-client-meeting-summary\',
        '.claude\skills\adhoc-dph-invoicing\',
        '.claude\skills\adhoc-smartscout-db\',
        '.claude\skills\investment-',
        '90_System\Skills\dph_invoicing\',
        '90_System\Skills\smartscout_db\',
        '90_System\Skills\investment_funnel\',
        '90_System\Skills\claude_code_mirror\'
    )
    foreach ($prefix in $ownerSpecificPrefixes) {
        if ($normalized.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    if ($normalized -like '90_System\Skills\meeting_attendees_people_sync\people_enrich*' -or
        $normalized -ieq '90_System\Skills\meeting_attendees_people_sync\SKILL.md' -or
        $normalized -ieq '90_System\Skills\meeting_attendees_people_sync\tests\test_people_enrich.py') {
        return $true
    }
    return $false
}

function Test-CredentialText {
    param([string]$Content)

    $pattern = '(?i)(?<![A-Za-z0-9.])xox[baprs]-[A-Za-z0-9-]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|TELEGRAM_BOT_TOKEN=[0-9]{8,}:[A-Za-z0-9_-]{20,}|"(?:client_secret|access_token|refresh_token|api_key|bot_token)"\s*:\s*"(?!<|example|replace|your)[A-Za-z0-9._:-]{20,}"'
    return [regex]::IsMatch($Content, $pattern)
}

function Test-ContainsCredential {
    param([string]$Path)

    $extension = [System.IO.Path]::GetExtension($Path).ToLowerInvariant()
    if (@('.md', '.txt', '.json', '.yaml', '.yml', '.toml', '.py', '.ps1', '.sh') -notcontains $extension) {
        return $false
    }

    return Test-CredentialText -Content (Get-Content -LiteralPath $Path -Raw)
}

function Copy-FileRelative {
    param(
        [string]$RelativeSource,
        [string]$RelativeDestination = $RelativeSource
    )
    $src = Join-Path $sourceRoot $RelativeSource
    $dst = Join-Path $Destination $RelativeDestination
    if ((Test-ExcludedExportPath -RelativePath $RelativeSource) -or (Test-ExcludedExportPath -RelativePath $RelativeDestination) -or (Test-ContainsCredential -Path $src)) {
        Write-Warning "Skipped excluded path: $RelativeSource"
        return
    }
    if ($PreserveExisting -and (Test-Path -LiteralPath $dst)) {
        return
    }
    Ensure-Directory -Path (Split-Path -Parent $dst)
    Copy-Item -LiteralPath $src -Destination $dst -Force
}

function Copy-TreeFiltered {
    param(
        [string]$RelativeSource,
        [string]$RelativeDestination,
        [string[]]$AllowedExtensions = @()
    )
    $srcRoot = Join-Path $sourceRoot $RelativeSource
    $dstRoot = Join-Path $Destination $RelativeDestination
    Ensure-Directory -Path $dstRoot

    Get-ChildItem -LiteralPath $srcRoot -Recurse -File | ForEach-Object {
        if ($AllowedExtensions.Count -gt 0 -and ($AllowedExtensions -notcontains $_.Extension.ToLowerInvariant())) {
            return
        }

        $relativePath = $_.FullName.Substring($srcRoot.Length).TrimStart('\')
        $sourceRelativePath = Join-Path $RelativeSource $relativePath
        if ((Test-ExcludedExportPath -RelativePath $sourceRelativePath) -or (Test-ContainsCredential -Path $_.FullName)) {
            Write-Warning "Skipped excluded path: $sourceRelativePath"
            return
        }
        $destinationPath = Join-Path $dstRoot $relativePath
        if ($PreserveExisting -and (Test-Path -LiteralPath $destinationPath)) {
            return
        }
        Ensure-Directory -Path (Split-Path -Parent $destinationPath)
        Copy-Item -LiteralPath $_.FullName -Destination $destinationPath -Force
    }
}

Ensure-Directory -Path $Destination

# System assets and automation code.
Copy-TreeFiltered -RelativeSource ".agents" -RelativeDestination ".agents"
Copy-TreeFiltered -RelativeSource ".claude\hooks" -RelativeDestination ".claude\hooks" -AllowedExtensions @(".py")
Copy-TreeFiltered -RelativeSource ".claude\skills" -RelativeDestination ".claude\skills"
Copy-TreeFiltered -RelativeSource "90_System\Skills" -RelativeDestination "90_System\Skills" -AllowedExtensions @(".md", ".py", ".ps1")
Copy-TreeFiltered -RelativeSource "90_System\Integrations\Documentation" -RelativeDestination "90_System\Integrations\Documentation" -AllowedExtensions @(".md")

$peopleSyncSkill = @'
---
name: "regular_people_sync"
description: "Create or update people notes from meetings and stored replied-thread participants."
---

# People sync

## What it does
- Finds attendees in meeting notes and participants in stored email threads.
- Creates or refreshes basic identity fields in `40_People/` and updates the people index.
- Leaves role, organization, team, and working style for manual review.

## Run
- Sync: `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync`
- Dry run: `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py sync --dry-run`
- Refresh layout: `.\.venv\Scripts\python.exe 90_System\Skills\meeting_attendees_people_sync\attendee_people_sync.py refresh-layout`
'@
Write-Utf8File -Path (Join-Path $Destination "90_System\Skills\meeting_attendees_people_sync\SKILL.md") -Content $peopleSyncSkill

Copy-FileRelative -RelativeSource "90_System\Integrations\telegram_bridge\README.md"
Copy-FileRelative -RelativeSource "90_System\Integrations\telegram_bridge\run_telegram_bridge.ps1"
Copy-FileRelative -RelativeSource "90_System\Integrations\telegram_bridge\start_telegram_bridge.ps1"
Copy-FileRelative -RelativeSource "90_System\Integrations\telegram_bridge\stop_telegram_bridge.ps1"
Copy-FileRelative -RelativeSource "90_System\Integrations\telegram_bridge\telegram_bridge.py"
Copy-FileRelative -RelativeSource "90_System\Integrations\telegram_bridge\send_telegram_notification.py"
Copy-FileRelative -RelativeSource "90_System\Integrations\telegram_bridge\tests\test_send_telegram_notification.py"
Copy-FileRelative -RelativeSource "90_System\Integrations\slack\app_manifest.readonly.yaml"
Copy-FileRelative -RelativeSource "90_System\Integrations\slack\app_manifest.writefuture.yaml"
Copy-FileRelative -RelativeSource "90_System\Integrations\slack\workspaces.example.json"
Copy-FileRelative -RelativeSource "90_System\TaskQueue\README.md"
Copy-FileRelative -RelativeSource "90_System\TaskQueue\Templates\Task_TEMPLATE.md"
Copy-FileRelative -RelativeSource ".gitignore"
$requirements = Get-Content -LiteralPath (Join-Path $sourceRoot "requirements.txt") |
    Where-Object { $_.Trim() -notmatch '^pyodbc(?:[<=>!~].*)?$' }
Write-Utf8File -Path (Join-Path $Destination "requirements.txt") -Content ($requirements -join [Environment]::NewLine)
Copy-FileRelative -RelativeSource "00_Mailbox\Templates\EmailSummary_TEMPLATE.md"
Copy-FileRelative -RelativeSource "00_Mailbox\Templates\EmailThread_TEMPLATE.md"
Copy-FileRelative -RelativeSource "00_Mailbox\Templates\SlackSummary_TEMPLATE.md"
Copy-FileRelative -RelativeSource "00_Mailbox\Templates\SlackThread_TEMPLATE.md"
Copy-FileRelative -RelativeSource "20_Meetings\Templates\MeetingNote_TEMPLATE.md"
Copy-FileRelative -RelativeSource "30_Projects\Templates\ProjectSnapshot_TEMPLATE.md"
Copy-FileRelative -RelativeSource "40_People\Templates\person_TEMPLATE.md"
Copy-FileRelative -RelativeSource "50_Areas\Area_TEMPLATE.md"
Copy-FileRelative -RelativeSource "80_Workblocks\README.md"
Copy-FileRelative -RelativeSource "80_Workblocks\_Template.md"
Copy-FileRelative -RelativeSource "60_SOPs\Templates\DailyBrief_TEMPLATE.md"
Copy-FileRelative -RelativeSource "60_SOPs\Templates\EmailThread_TEMPLATE.md"
Copy-FileRelative -RelativeSource "60_SOPs\Templates\WeeklyReview_TEMPLATE.md"
Copy-FileRelative -RelativeSource ".codex\rules\vault.rules"

# Task queue runtime folders.
@(
    "90_System\TaskQueue\pending",
    "90_System\TaskQueue\running",
    "90_System\TaskQueue\failed",
    "90_System\TaskQueue\done",
    "10_DailyBriefs",
    "20_Meetings",
    "30_Projects",
    "40_People",
    "50_Areas",
    "70_Exports",
    "80_Workblocks",
    "_attachments"
) | ForEach-Object {
    Ensure-Directory -Path (Join-Path $Destination $_)
}

@(
    "90_System\TaskQueue\pending\.gitkeep",
    "90_System\TaskQueue\running\.gitkeep",
    "90_System\TaskQueue\failed\.gitkeep",
    "90_System\TaskQueue\done\.gitkeep"
) | ForEach-Object {
    Write-Utf8File -Path (Join-Path $Destination $_) -Content ""
}

$readme = @'
# Agentic Vault

A reusable, Obsidian-friendly vault skeleton for personal operating systems with repo-local agent skills and automation wrappers.

## Included

- Markdown-first vault structure for mailbox, daily briefs, meetings, projects, people, and areas
- Repo-local Codex and Claude guidance
- Wrapper skills in `.agents/` plus runnable automation code in `90_System/Skills/`
- Task queue, integration docs, and note templates

## Excluded on purpose

- Personal notes, meeting history, people records, and area/project content
- Secrets, OAuth tokens, runtime state, logs, and machine-local settings
- Obsidian workspace state and ad-hoc attachments

## First setup

1. Open the vault in Obsidian.
2. Review and customize `AGENTS.md`, `SOUL.md`, `MEMORY.md`, and `60_SOPs/_HowIWork.md`.
3. Add your own secrets and OAuth files under `90_System/secrets/` without committing them.
4. Install Python dependencies from `requirements.txt` into a local virtual environment.
5. Adjust `.codex/config.toml` if you want this vault to work with additional external repos.
'@

$agents = @'
# Agent Instructions (Agentic Vault)

Scope: everything in this repository.

## What this repo is
- This is an Obsidian vault (Markdown-first) designed as a reusable second-brain operating system.
- When doing any task, first check relevant local files.
- Prefer Obsidian wikilinks for durable connections between projects, people, areas, and meetings.

## Session bootstrap
- In every session, read `AGENTS.md`, `SOUL.md`, and `MEMORY.md` from the repo root.
- Update `MEMORY.md` only when a new lesson is likely to save time or prevent a repeated mistake.

## Canonical paths for locally stored data
- Emails live under `00_Mailbox/YYYY/MM/DD`. Email summaries and threads use templates in `00_Mailbox/Templates/`.
- Daily briefs live under `10_DailyBriefs/YYYY/MM/`.
- Meetings live under `20_Meetings/YYYY/MM/DD/`. Each meeting record uses `20_Meetings/Templates/MeetingNote_TEMPLATE.md`.
- Projects live under `30_Projects/<ProjectFolder>/`. Snapshots use `30_Projects/Templates/ProjectSnapshot_TEMPLATE.md`.
- People live under `40_People/`. Each person record uses `40_People/Templates/person_TEMPLATE.md`.
- Areas live under `50_Areas/`.
- Workblocks live under `80_Workblocks/` and provide short-lived session handoff state; they are not authoritative project documentation.

## Non-negotiables
- ABSOLUTELY NEVER USE AVAILABLE TOKENS TO CUSTOM INTERACTION WITH EXTERNAL SERVICES. EXTERNAL SERVICES CAN ONLY BE QUERIED BY DEDICATED SKILLS.
- Prefer stable paths and simple naming conventions.
- Keep any changes Obsidian-friendly.
- Do not delete, move, or rename existing user files unless explicitly asked.
- For local filesystem editing skills, never modify source files in place outside the vault. Read from the selected path, but write new or updated artifacts only under `70_Exports/YYYY/MM/DD/<file_name>`.
- For edits of existing external files, first create a copy in `70_Exports/YYYY/MM/DD/`, edit only that exported copy, and report both the original and exported paths.
- Do not restructure folders unless explicitly asked.
- Default to short bullets over paragraphs.
- Use YAML frontmatter only when it materially helps.

## File naming
- Daily briefs: `10_DailyBriefs/YYYY/MM/YYYY-MM-DD_Daily_Brief.md`
- Meetings: `20_Meetings/YYYY/MM/DD/HHmm - Title.md`
- Projects: keep a stable project note name; snapshots use `... - Snapshot` if needed
- People: `40_People/Person Name.md`
- Areas: `50_Areas/Area Name/`
- Workblocks: `80_Workblocks/<Scope> - <Intent>.md`; keep the Windows-safe filename at most 120 characters and add a short source-session ID only to resolve a collision.

## When adding new content
- If the change affects a project, also update `30_Projects/_Projects.md`.
- If the change creates a meeting note, add it to `20_Meetings/_MeetingIndex.md`.
- If the change adds people context, update `40_People/` and `40_People/_PeopleIndex.md`.
- If the change adds or updates an area, reflect it in `50_Areas/_Areas.md`.

## Workblock protocol
- At the start of every session, use `90_System/Skills/workblocks/workblocks.py list --statuses active,blocked --query "<current topic>"` to find relevant workblocks before planning or editing; create a new workblock only when the work has a real continuation beyond the current session.
- Load at most one unambiguous relevant workblock. If multiple candidates remain relevant, do not guess: ask the user to select one. Verify its current state against the referenced vault files before relying on it.
- Treat `80_Workblocks/` as operational handoff memory, not authoritative project documentation. Keep one stable file per continuing intent and store dates only in YAML frontmatter.
- Use only `active`, `blocked`, or `completed` for `status`; use a project/area wikilink or `general` for `scope`; record source session IDs in the body and never copy raw transcripts into a workblock.
- Before the final answer, update the workblock used in the session with verified facts only: goal, current state, next action, blocker or decision, key files, and source session IDs. Preserve a newer live state when adding historical context.
- Change a workblock to `completed` only when its objective done condition is demonstrably satisfied or the user confirms completion. Uncertain historical state defaults to `completed`; use `blocked` only for an explicit unresolved blocker.
- End every final response with exactly one receipt: `Workblock: updated <path>`, `Workblock: read, unchanged <path>`, or `Workblock: not needed — one-off task`.

## Skill routing
- Skills are available in `.agents/skills/`.
- Use `regular_*` for deterministic maintenance flows.
- Use `bulk_*` for deterministic backfills.
- Use `adhoc_*` for one-off external-system or local-file work.

## Agent deliverables
- Prefer actionable checklists at the end of outputs.
- If something is ambiguous, ask 1 to 3 concrete questions.

## Deferred task queue
- Deferred queue root: `90_System/TaskQueue/`
- Use this when work should be deferred because the current run cannot or should not finish it now.
- Canonical helper: `90_System/Skills/deferred_task_queue/task_queue.py`
'@

$soul = @'
# SOUL

This defines the default personality of the agent working in this vault.

## Identity
- I act as a pragmatic chief-of-staff and operating-system maintainer for the vault owner.
- I optimize for useful outcomes, fast orientation, and low-friction maintenance.
- I communicate directly, positively, and helpfully.

## Behavioral Defaults
- I preserve the current structure: prefer stable paths, stable names, and Obsidian-friendly Markdown.
- I keep outputs concise and actionable: prefer short bullets and direct next steps.
- I always make the smallest change that fully solves the task.
- I never do extra work I was not asked to do.
- I reuse existing patterns, templates, and note structures before inventing new ones.
- I ask clarifying questions when information is missing.
- I aim to build trust through competence.
'@

$memory = @'
# MEMORY

## Preferences
- Keep bullets short and operational.

## Learned Rules
- Add only durable lessons that are likely to save time later.
- Prefer wrapper skills over direct external-service access.
- Keep runtime state, logs, and secrets out of version control.

## Useful Pointers
- Link important recurring files or indexes when they are not obvious.

## Known Pitfalls
- Record only mistakes worth actively avoiding next time.
'@

$claude = @'
# Claude Instructions (Agentic Vault)

This file is generated or maintained from the repo-local guidance. Treat `AGENTS.md`, `SOUL.md`, and `MEMORY.md` as the source of truth.

## Startup
- At the start of each session, read `AGENTS.md`, `SOUL.md`, and `MEMORY.md` from the repo root.

## Behavioral defaults
- Preserve the current structure and stay Obsidian-friendly.
- Keep outputs concise and actionable.
- Reuse templates and existing note patterns before inventing new ones.

## Non-negotiables
- Keep external-service access inside dedicated skills.
- Do not delete, move, or rename files unless explicitly asked.
- For outside-vault file edits, work on exported copies under `70_Exports/YYYY/MM/DD/`.

## Workblock protocol
- At session start, search `80_Workblocks/` for relevant `active` or `blocked` workblocks, load at most one unambiguous result, and verify it against current files.
- Create or update a workblock only for continuing work. Use verified facts, keep source session IDs instead of transcripts, and mark `completed` only when the done condition is proven or confirmed.
- End every final response with exactly one receipt: `Workblock: updated <path>`, `Workblock: read, unchanged <path>`, or `Workblock: not needed — one-off task`.
'@

$skills = @'
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
'@

$codexReadme = @'
# Codex setup (repo-local)

This vault includes repo-local Codex configuration, command approval rules, and wrapper skills so contributors can use the same automations out of the box.

## What's included
- `.codex/config.toml`: default sandbox, approvals, model, and allowed roots
- `.codex/rules/*.rules`: optional command approval rules
- `.codex/file_access_policy.toml`: human-readable allow and deny patterns
- `.agents/skills/**/SKILL.md`: repo-local wrapper skills

## Notes
- Adjust `.codex/config.toml` for your local machine and any approved external repos.
- If your Codex installation does not pick up repo-local rules automatically, copy the relevant `.rules` file into your user rules directory.
'@

$escapedDestination = $Destination.Replace("\", "\\")

$codexConfig = @"
model = "gpt-5.4"

approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true

allowed_roots = [
  "$escapedDestination",
]
"@

$codexPolicy = @'
# File access policy (repo-local, human-readable).
#
# Repo-local globs below describe the vault itself.

[read]
allow = ["**/*"]
deny = [
  ".git/**",
  ".venv/**",
  "90_System/secrets/**",
]

[edit]
allow = [
  "**/*.md",
  "**/*.toml",
  "**/*.rules",
  "**/*.py",
  "**/*.ps1",
  "requirements.txt",
  ".gitignore",
]
deny = [
  ".git/**",
  ".venv/**",
  ".obsidian/**",
  "_attachments/**",
  "OneNoteNotes/**",
]

[delete]
allow = []
deny = ["**/*"]
'@

$claudeReadme = @'
# Claude setup (repo-local)

This vault can also expose mirrored Claude-facing skills and hooks.

## Included
- `.claude/settings.json`
- `.claude/hooks/`
- `.claude/skills/`
- `CLAUDE.md`

## Notes
- Keep machine-specific access in your user-level Claude settings.
- Regenerate or update mirrored files after changing repo-local guidance or skills.
'@

$claudeSettings = @'
{
  "permissions": {
    "allow": [
      "Bash(git status*)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git show*)",
      "Bash(git rev-parse*)",
      "Bash(git ls-files*)"
    ],
    "deny": [
      "Read(.git/**)",
      "Read(.venv/**)",
      "Read(.obsidian/**)",
      "Read(_attachments/**)",
      "Read(OneNoteNotes/**)",
      "Read(90_System/secrets/**)",
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Edit(.git/**)",
      "Edit(.venv/**)",
      "Edit(.obsidian/**)",
      "Edit(_attachments/**)",
      "Edit(OneNoteNotes/**)",
      "Edit(90_System/secrets/**)",
      "Write(.git/**)",
      "Write(.venv/**)",
      "Write(.obsidian/**)",
      "Write(_attachments/**)",
      "Write(OneNoteNotes/**)",
      "Write(90_System/secrets/**)",
      "MultiEdit(.git/**)",
      "MultiEdit(.venv/**)",
      "MultiEdit(.obsidian/**)",
      "MultiEdit(_attachments/**)",
      "MultiEdit(OneNoteNotes/**)",
      "MultiEdit(90_System/secrets/**)"
    ]
  }
}
'@

$agentPrompts = Get-Content -Raw -LiteralPath (Join-Path $sourceRoot "AgentPrompts.md")
$startHere = Get-Content -Raw -LiteralPath (Join-Path $sourceRoot "60_SOPs\StartHere.md")
$howIWork = Get-Content -Raw -LiteralPath (Join-Path $sourceRoot "60_SOPs\_HowIWork.md")
$howIWork = $howIWork -replace '1\. Work \(FLO\)', '1. Work'
$agentGuide = Get-Content -Raw -LiteralPath (Join-Path $sourceRoot "60_SOPs\_AgentGuide.md")
$mailbox = Get-Content -Raw -LiteralPath (Join-Path $sourceRoot "00_Mailbox\_Mailbox.md")

$meetingIndex = @'
---
type: index
---

# Meeting Index

## Conventions
- Filename: `20_Meetings/YYYY/MM/DD/HHmm - Title.md`
- Create notes from: `20_Meetings/Templates/MeetingNote_TEMPLATE.md`

## Example month
- [[20_Meetings/2026/01/15/1000 - Example meeting]]
'@

$projectsIndex = @'
---
type: index
---

# Projects

Legend
- Status: Green = on track, Yellow = watch, Red = needs intervention

## Active projects

| Project | Area | Status | Next 1 to 3 actions | Snapshot |
|---|---|---|---|---|
| [[30_Projects/ExampleProject/Example Project]] | [[50_Areas/Example Area]] | Green | - Define outcome<br>- Confirm next milestone | [[30_Projects/ExampleProject/Example Project - Snapshot]] |

## On hold / backlog
- [[Someday Project]] (notes: ...)
'@

$peopleIndex = @'
---
type: index
---

# People Index

## Key people
- [[Person Name]] (role: , team: , last touch: YYYY-MM-DD)
- [[Another Person]] (role: , team: , last touch: YYYY-MM-DD)

## Notes
- Keep people notes short: working style, context, last decisions, open loops.
'@

$areasIndex = @'
---
type: index
---

# Areas

Areas are ongoing responsibilities that need maintenance, not one-off completion.

## Active areas
- [[50_Areas/Personal Activities]]
- [[50_Areas/Example Area]]

## How to use this section
- Link projects to an area when they serve a broader responsibility.
- Keep area notes focused on routines, standards, recurring decisions, and open loops.
- Use stable area names so links stay predictable across the vault.
'@

Write-Utf8File -Path (Join-Path $Destination "README.md") -Content $readme
Write-Utf8File -Path (Join-Path $Destination "AGENTS.md") -Content $agents
Write-Utf8File -Path (Join-Path $Destination "SOUL.md") -Content $soul
Write-Utf8File -Path (Join-Path $Destination "MEMORY.md") -Content $memory
Write-Utf8File -Path (Join-Path $Destination "CLAUDE.md") -Content $claude
Write-Utf8File -Path (Join-Path $Destination "SKILLS.md") -Content $skills
Write-Utf8File -Path (Join-Path $Destination "AgentPrompts.md") -Content $agentPrompts
Write-Utf8File -Path (Join-Path $Destination ".codex\README.md") -Content $codexReadme
Write-Utf8File -Path (Join-Path $Destination ".codex\config.toml") -Content $codexConfig
Write-Utf8File -Path (Join-Path $Destination ".codex\file_access_policy.toml") -Content $codexPolicy
Write-Utf8File -Path (Join-Path $Destination ".claude\README.md") -Content $claudeReadme
Write-Utf8File -Path (Join-Path $Destination ".claude\settings.json") -Content $claudeSettings
Write-Utf8File -Path (Join-Path $Destination ".claude\settings.local.example.json") -Content "{`n  `"additionalDirectories`": []`n}`n"
Write-Utf8File -Path (Join-Path $Destination "60_SOPs\StartHere.md") -Content $startHere
Write-Utf8File -Path (Join-Path $Destination "60_SOPs\_HowIWork.md") -Content $howIWork
Write-Utf8File -Path (Join-Path $Destination "60_SOPs\_AgentGuide.md") -Content $agentGuide
Write-Utf8File -Path (Join-Path $Destination "00_Mailbox\_Mailbox.md") -Content $mailbox
Write-Utf8File -Path (Join-Path $Destination "20_Meetings\_MeetingIndex.md") -Content $meetingIndex
Write-Utf8File -Path (Join-Path $Destination "30_Projects\_Projects.md") -Content $projectsIndex
Write-Utf8File -Path (Join-Path $Destination "40_People\_PeopleIndex.md") -Content $peopleIndex
Write-Utf8File -Path (Join-Path $Destination "50_Areas\_Areas.md") -Content $areasIndex

Write-Output "Sanitized agentic vault exported to $Destination"
