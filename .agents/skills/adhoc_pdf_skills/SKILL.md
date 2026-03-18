---
name: "adhoc_pdf_skills"
description: "Use when tasks involve reading, creating, or reviewing PDF files in this vault. Prefer rendered-page checks when layout matters."
---

# Ad-hoc PDF Skills

## When to use
- Read or review PDF content where layout and visuals matter.
- Create PDFs programmatically with reliable formatting.
- Extract text or tables from PDFs for analysis.

## Workflow
1. Prefer visual review by rendering pages to images when possible.
2. Use `reportlab` for newly generated PDFs.
3. Use `pdfplumber` or `pypdf` for extraction and quick checks.
4. For a new PDF, write the artifact only under `70_Exports\YYYY\MM\DD\<file_name>.pdf`.
5. For an edit request, read the original file, create a copy under `70_Exports\YYYY\MM\DD\<original-file-name>.pdf`, and update only that exported copy.
6. Re-render after meaningful updates and verify spacing, alignment, and legibility.
7. In the final response, state that the source file was left untouched and provide the exported path for manual pickup.

## Repo conventions
- Write all new or updated artifacts only under `70_Exports\YYYY\MM\DD\`.
- Keep temporary render output under the same dated tree, for example `70_Exports\YYYY\MM\DD\tmp\pdf\`.
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
.\.venv\Scripts\python.exe -m pip install reportlab pdfplumber pypdf
```

System tool for visual rendering:
- Poppler / `pdftoppm`

If `pdftoppm` is missing, continue with extraction or generation work and note that visual QA could not be completed.

## Rendering command
```powershell
pdftoppm -png <exported.pdf> 70_Exports\YYYY\MM\DD\tmp\pdf\page
```

## Quality checks
- Check headers, footers, pagination, tables, and image clarity.
- Avoid clipped text, overlapping elements, unreadable glyphs, and broken tables.
- Remove intermediate renders unless the user wants them kept.
