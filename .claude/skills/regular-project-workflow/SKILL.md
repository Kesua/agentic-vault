---
name: "regular-project-workflow"
description: "Workflow guide: maintain project notes, snapshots, project index, and relinking using the existing vault structure."
---

# Regular Project Workflow

This is a Claude Code mirror of `regular_project_workflow` from `.agents/skills/`.
Original source: `.agents/skills/regular_project_workflow/SKILL.md`
Skill class: `regular`

This is a documentation-first wrapper for the project workflow that already exists in the vault.

## Canonical paths
- Main note: `30_Projects/<ProjectFolder>/<ProjectName>.md`
- Snapshot: `30_Projects/<ProjectFolder>/<ProjectName> - Snapshot.md`
- Index: `30_Projects/_Projects.md`
- Template: `30_Projects/Templates/ProjectSnapshot_TEMPLATE.md`

## Recommended workflow
1. Create or update the project note in `30_Projects/<ProjectFolder>/`.
2. Create or refresh the snapshot note from `30_Projects/Templates/ProjectSnapshot_TEMPLATE.md`.
3. Update `30_Projects/_Projects.md` with status and next 1-3 actions.
4. Run `regular_create_links` so related Daily Briefs, Meetings, and Project notes pick up the latest project aliases.

## Related docs
- Linking automation: `90_System/Skills/create_links/SKILL.md`
- Wrapper: `.agents/skills/regular_create_links/SKILL.md`
