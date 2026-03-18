---
name: "regular_people_workflow"
description: "Workflow guide: maintain people notes, people index, and relinking using the existing vault structure."
---

# Regular People Workflow

This is a documentation-first wrapper for the people workflow that already exists in the vault.

## Canonical paths
- People note: `40_People/<Person Name>.md`
- Index: `40_People/_PeopleIndex.md`

## Recommended workflow
1. Create or update the person note in `40_People/`.
2. Keep aliases and emails accurate so matching stays reliable.
3. Update `40_People/_PeopleIndex.md`.
4. Run `regular_create_links` so related Daily Briefs, Meetings, and Project notes pick up the latest people aliases.

## Related docs
- Linking automation: `90_System/Skills/create_links/SKILL.md`
- Wrapper: `.agents/skills/regular_create_links/SKILL.md`
