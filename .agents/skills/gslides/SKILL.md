---
name: "gslides"
description: "Repo-local Google Slides skill: read slide structure, create presentations, and update slide text."
---

# Google Slides

This is a **repo-local** Google Slides skill backed by `90_System/Skills/google_drive_assistant/google_drive_assistant.py`.

## Scope
- Read presentation text slide by slide
- Create a new presentation
- Replace slide text across an existing presentation
- Update one text box by shape id when a stable object id is known

## Run (from the vault repo root)
- Read presentation text:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py get-presentation-text --account both --presentation-id <presentation_id_or_url>`
- Create a new presentation:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py create-presentation --account both --title "Weekly Review"`
- Replace text across slides:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py replace-slide-text --account both --presentation-id <presentation_id_or_url> --find "Draft" --replace "Approved"`
- Update one shape:
  - `.\.venv\Scripts\python.exe 90_System\Skills\google_drive_assistant\google_drive_assistant.py update-slide-shape-text --account both --presentation-id <presentation_id_or_url> --shape-id <object_id> --text "Updated slide body"`
- Full docs:
  - `90_System/Skills/google_drive_assistant/SKILL.md`
