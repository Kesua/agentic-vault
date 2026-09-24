# Workblocks

`80_Workblocks/` is the vault's short-lived operational memory between agent sessions. A workblock records the latest verified handoff for one continuing work intent; project and area notes remain authoritative.

## Lifecycle

- Check relevant `active` and `blocked` workblocks at session start with:

  ```powershell
  .\.venv\Scripts\python.exe 90_System\Skills\workblocks\workblocks.py list --statuses active,blocked --query "<current topic>"
  ```

- Read at most one unambiguous result and verify it against current vault files. Ask the user when several candidates remain relevant.
- Create a file only when work is expected to continue beyond the current session. One-off tasks use no workblock.
- Update the same stable file before the final response, using verified facts only.
- Mark `completed` only when the done condition is proven or confirmed. Keep completed files in this folder for searchable history.

## Format

- Filename: `<Scope> - <Intent>.md`, Windows-safe and no longer than 120 characters. Add ` - <short-session-id>` only for a collision.
- `status`: `active`, `blocked`, or `completed`.
- `scope`: a project/area wikilink or `general`.
- `confidence`: `high`, `medium`, or `low`; mandatory for historical backfill.
- Put session IDs in `Source sessions`; never put raw transcripts here.
- Dates belong in YAML, not the filename.

Start from [`_Template.md`](_Template.md). Validate all workblocks with:

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\workblocks\workblocks.py validate
```

Every agent final response ends with one receipt:

- `Workblock: updated <path>`
- `Workblock: read, unchanged <path>`
- `Workblock: not needed — one-off task`
