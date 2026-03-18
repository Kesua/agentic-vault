---
name: "adhoc_word_docs"
description: "Use when the task involves reading, creating, or editing `.docx` files in this vault. Prefer `python-docx` and the bundled renderer helper for layout checks."
---

# Ad-hoc Word Docs

## When to use
- Read or review `.docx` content where layout matters.
- Create or edit Word documents with structured formatting.
- Validate page layout before handing the file back.

## Workflow
1. Prefer a visual review loop when layout matters.
2. Use `python-docx` for document edits and generation.
3. For a new document, write the artifact only under `70_Exports\YYYY\MM\DD\<file_name>.docx`.
4. For an edit request, read the original file, create a copy under `70_Exports\YYYY\MM\DD\<original-file-name>.docx`, and edit only that exported copy.
5. Re-render after meaningful changes with the local helper:
   - `.\.venv\Scripts\python.exe .agents\skills\adhoc_word_docs\scripts\render_docx.py <exported.docx> --output_dir 70_Exports\YYYY\MM\DD\tmp\docx_pages`
6. If visual rendering is unavailable, fall back to text inspection and call out layout risk.
7. In the final response, state that the source file was left untouched and provide the exported path for manual pickup.

## Repo conventions
- Write all new or updated artifacts only under `70_Exports\YYYY\MM\DD\`.
- Keep temporary render output under the same dated tree, for example `70_Exports\YYYY\MM\DD\tmp\docx_pages\`.
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
.\.venv\Scripts\python.exe -m pip install python-docx pdf2image
```

System tools for rendering:
- LibreOffice / `soffice`
- Poppler / `pdftoppm`

If those system tools are missing, continue with `python-docx` edits and explicitly note that visual validation was not possible.

## Helper files
- Renderer: `.agents\skills\adhoc_word_docs\scripts\render_docx.py`

## Quality checks
- Verify headings, spacing, tables, and page breaks.
- Avoid clipped text, broken tables, and default-template styling.
- Clean up temporary render output unless the user wants to keep it.
