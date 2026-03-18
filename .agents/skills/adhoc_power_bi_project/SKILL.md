---
name: "adhoc_power_bi_project"
description: "Wrapper skill: review and edit Power BI Project (PBIP) folders safely, preferring PBIR and TMDL over binary PBIX work."
---

# Ad-hoc Power BI Project

This is a **wrapper** skill for the workflow guidance in `90_System/Skills/power_bi_project/`.

## Scope
- Inspect a Power BI Project folder (`.pbip`)
- Review or edit PBIR report files
- Review or edit TMDL semantic model files
- Prepare an exported working copy when the source project is outside the vault

## Rules
- Prefer `PBIP` over `PBIX` for agent edits.
- Treat `PBIX` as a conversion and delivery format, not the working format.
- Use Power BI Desktop for `PBIX -> PBIP` and `PBIP -> PBIX` through `File > Save As`.
- Do not edit unsupported preview files externally:
  - `report.json`
  - `mobileState.json`
  - `semanticModelDiagramLayout.json`
  - `diagramLayout.json`
- If the source project sits outside the vault, create and edit only an exported copy under `70_Exports\YYYY\MM\DD\`.

## Typical work
- Fix DAX or TMDL definitions
- Adjust report JSON in PBIR
- Repoint `definition.pbir` to the correct semantic model path
- Review project structure, merge conflicts, or source-control diffs
- Document what the project contains and which files are safe to touch

## Run
- Read the workflow:
  - `90_System/Skills/power_bi_project/SKILL.md`

## Handoff
- After edits, reopen the project in Power BI Desktop.
- Validate report rendering, model refresh, and pending query changes.
- Save as `PBIX` only if a binary handoff or upload flow requires it.
