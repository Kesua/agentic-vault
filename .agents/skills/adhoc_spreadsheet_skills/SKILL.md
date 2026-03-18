---
name: "adhoc_spreadsheet_skills"
description: "Use when tasks involve creating, editing, analyzing, or formatting spreadsheets in this vault. Prefer `openpyxl` for `.xlsx` and `pandas` for tabular analysis."
---

# Ad-hoc Spreadsheet Skills

## When to use
- Create new workbooks with formulas and formatting.
- Read or analyze `.xlsx`, `.csv`, or `.tsv` files.
- Modify existing spreadsheets without breaking formulas, references, or style.
- Prepare charts, summaries, and export-ready tables.

## Workflow
1. Confirm whether the task is create, edit, analyze, or visualize.
2. Use `openpyxl` for `.xlsx` editing and formatting.
3. Use `pandas` for analysis and CSV/TSV work.
4. Preserve formulas instead of hardcoding derived values.
5. If layout matters, render via LibreOffice plus Poppler when available.
6. For a new workbook or table export, write the artifact only under `70_Exports\YYYY\MM\DD\<file_name>`.
7. For an edit request, read the original file, create a copy under `70_Exports\YYYY\MM\DD\<original-file-name>`, and edit only that exported copy.
8. Keep intermediates in the same dated export tree and clean them up when finished.
9. In the final response, state that the source file was left untouched and provide the exported path for manual pickup.

## Repo conventions
- Write all new or updated artifacts only under `70_Exports\YYYY\MM\DD\`.
- Keep temporary files under the same dated tree, for example `70_Exports\YYYY\MM\DD\tmp\spreadsheets\`.
- Never overwrite, rename, move, or save back to the original source path.
- Keep filenames stable and descriptive.

## Dependencies
Install into the repo virtual environment with `pip`, not `uv`.

Primary install:
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Targeted install:
```powershell
.\.venv\Scripts\python.exe -m pip install openpyxl pandas matplotlib
```

If `matplotlib` warns about an unwritable cache folder, set a repo-local cache first:
```powershell
$env:MPLCONFIGDIR = (Resolve-Path "70_Exports\\YYYY\\MM\\DD\\tmp\\matplotlib").Path
```

System tools for visual review:
- LibreOffice / `soffice`
- Poppler / `pdftoppm`

If rendering tools are unavailable, preserve workbook structure and note that final layout should be checked locally.

## Helper files
- Example scripts: `.agents\skills\adhoc_spreadsheet_skills\references\examples\openpyxl\`

## Formula and formatting rules
- Use formulas for derived values.
- Avoid volatile formulas unless required.
- Use appropriate number, date, percentage, and currency formats.
- Preserve existing formatting when editing an existing workbook.
- Keep totals simple and auditable.

## Quality checks
- Verify formulas, references, widths, row heights, and text overflow.
- Check for `#REF!`, `#DIV/0!`, `#VALUE!`, `#N/A`, and circular references.
- Remove intermediate render files unless the user wants them kept.
