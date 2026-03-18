---
name: "power_bi_project"
description: "Use when the task involves reviewing or editing a Power BI Project (PBIP). Prefer PBIR for report edits and TMDL for semantic model edits, and avoid unsupported files during preview."
---

# Power BI Project

## When to use
- Review or edit a Power BI Project (`.pbip`) instead of a binary `PBIX`.
- Inspect or change report definition files in PBIR format.
- Inspect or change semantic model files in TMDL format.
- Review DAX, report-level measures, Power Query carry-over, dataset references, themes, and project structure.

## Do not use for
- Direct in-place editing of a `PBIX` file.
- Power BI Desktop UI operations such as `Save As`, publish, refresh, or cloud deployment.
- Unsupported preview files that Microsoft says not to edit externally.

## Microsoft-documented structure
- A `PBIP` root commonly contains:
  - `<ProjectName>.pbip`
  - `<ProjectName>.Report\`
  - `<ProjectName>.SemanticModel\`
  - `.gitignore`
- The `.pbip` file is a pointer to the report folder.
- The report folder is controlled by `definition.pbir` and can store either:
  - legacy `report.json` (PBIR-Legacy, not supported for external editing), or
  - `definition\` (PBIR, supported for external editing)
- The semantic model folder is controlled by `definition.pbism` and can store either:
  - `model.bim` (TMSL), or
  - `definition\` (TMDL, supported for text-based editing)

## Safe edit surfaces
- Report:
  - `<ProjectName>.Report\definition.pbir`
  - `<ProjectName>.Report\definition\**\*.json` in PBIR format
  - `<ProjectName>.Report\RegisteredResources\*` only for already registered resources
- Semantic model:
  - `<ProjectName>.SemanticModel\definition.pbism`
  - `<ProjectName>.SemanticModel\definition\**\*.tmdl`
  - `<ProjectName>.SemanticModel\DAXQueries\*`
  - `<ProjectName>.SemanticModel\TMDLScripts\*`
- Microsoft says PBIR files have public JSON schemas and Power BI Desktop validates changed PBIR files on open.
- Microsoft says TMDL is human-friendly and intended for source control and co-development.

## Files to avoid editing externally
- Report:
  - `report.json`
  - `mobileState.json`
  - `semanticModelDiagramLayout.json`
- Semantic model:
  - `diagramLayout.json`
- Treat `.platform`, `.pbi\localSettings.json`, and `.pbi\cache.abf` as system/local artifacts unless the task is explicitly about them.

## Workflow
1. Confirm the input is a `PBIP` project or a folder containing `.pbip`, `.Report`, and `.SemanticModel`.
2. If the source project is outside the vault, do not edit it in place.
3. For an external source, create an exported working copy under `70_Exports\YYYY\MM\DD\<ProjectName>\` and edit only that copy.
4. Inspect which formats are present:
   - Prefer PBIR over legacy `report.json`.
   - Prefer TMDL over `model.bim`.
5. Keep edits narrow and textual:
   - DAX and TMDL changes in semantic model files
   - report JSON changes in PBIR files
   - dataset reference changes in `definition.pbir`
   - already-loaded themes or resource files in `RegisteredResources\`
6. Do not promise unsupported edits to preview-only files.
7. Save edited text as UTF-8 without BOM when working outside Power BI Desktop.
8. Tell the user to reopen or restart Power BI Desktop after external edits so the project reloads from disk.
9. Tell the user that `PBIX -> PBIP` and `PBIP -> PBIX` conversion is done in Power BI Desktop with `File > Save As`.

## Practical editing options
- Report-side options:
  - Copy pages, visuals, or bookmarks between PBIR projects
  - Batch-edit visual JSON
  - Adjust report-level filters and formatting in PBIR
  - Change the semantic model reference in `definition.pbir`
- Model-side options:
  - Edit measures, tables, roles, cultures, perspectives, and calculation metadata in TMDL
  - Review pending Power Query work in `.pbi\unappliedChanges.json` carefully
- Resource-side options:
  - Swap pre-registered theme files, images, or private custom visuals in `RegisteredResources\`

## Cautions
- If `.pbi\unappliedChanges.json` exists, Power BI Desktop can overwrite semantic model query metadata when the pending changes are applied.
- If `cache.abf` exists, Power BI Desktop can load data and overwrite the model definition from project metadata on open.
- Keep root paths short on Windows because Microsoft documents path length issues with PBIP projects.
- Avoid direct save targets on OneDrive or SharePoint; prefer a local path first.

## Expected final response
- State whether the project used PBIR, TMDL, legacy `report.json`, or `model.bim`.
- List the edited files.
- Call out any unsupported files intentionally left untouched.
- If the source was external, report both the original path and the exported working-copy path.
- End with a short checklist for Desktop validation:
  - open project
  - refresh/apply changes if needed
  - save as `PBIX` if required
  - publish from Desktop or upload the resulting `PBIX`

## Sources
- https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-overview
- https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-report
- https://learn.microsoft.com/en-us/power-bi/developer/projects/projects-dataset
- https://learn.microsoft.com/en-us/power-bi/developer/embedded/projects-enhanced-report-format
