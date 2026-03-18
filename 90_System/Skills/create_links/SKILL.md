---
name: "regular_create_links"
description: "Regular linking hygiene: scan markdown for exact person/project/area aliases and convert eligible raw mentions into canonical Obsidian wikilinks."
---

# Create links

## What it does
- Builds an alias registry from structured entity notes only:
  - `40_People/**/*.md` with `type: person`
  - `30_Projects/**/*.md` with `type: project`
  - `50_Areas/**/*.md` with `type: area`
- Scans these targets for exact, case-sensitive alias matches:
  - `00_Mailbox/**/*.md`
  - `10_DailyBriefs/**/*.md`
  - `20_Meetings/**/*.md`
  - `30_Projects/**/*.md`
  - `50_Areas/**/*.md`
- Rewrites only eligible plain-text mentions into Obsidian wikilinks.

## When to use it
- After updating people notes in `40_People/` (aliases, emails, names)
- After updating project notes in `30_Projects/` (aliases, canonical project names)
- After updating area notes in `50_Areas/` (aliases, canonical area names)
- After meeting syncs, mailbox exports, or Daily Brief refreshes when you want new plain-text mentions linked

## Skip rules
- Never rewrites YAML alias definitions in source-of-truth entity notes.
- Skips any file whose leading metadata declares `type: person`, `type: project`, or `type: area`.
- Skips any markdown file located inside a git submodule.
- Skips protected spans:
  - leading frontmatter / leading YAML-like metadata block
  - existing wikilinks `[[...]]`
  - markdown links `[label](url)`
  - bare URLs / link schemes
  - fenced code blocks
  - inline code
- Uses exact, case-sensitive matching with non-alphanumeric boundaries only.
- If the same alias exists in multiple entity notes, that alias is logged as ambiguous and not linked.

## Link format
- People: `[[Person Name|Alias]]`
- Projects: `[[30_Projects/ProjectFolder/ProjectNote|Alias]]`
- Areas: `[[50_Areas/Area Note|Alias]]`

## Commands (Windows)
- Dry run:
  - `.\.venv\Scripts\python.exe 90_System\Skills\create_links\create_links.py sync --dry-run`
- Sync:
  - `.\.venv\Scripts\python.exe 90_System\Skills\create_links\create_links.py sync`

## Notes
- YAML aliases in person/project/area notes are the source of truth.
- The skill never rewrites those alias lists.
- This is the main linking hygiene step for Mailbox, Daily Briefs, Meetings, Projects, People, and Areas workflows in this vault.
