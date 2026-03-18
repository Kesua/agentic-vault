---
name: "regular-web-daily-brief"
description: "Wrapper skill: refresh the Daily News block in today’s Daily Brief."
---

# Regular Web Daily Brief

This is a Claude Code mirror of `regular_web_daily_brief` from `.agents/skills/`.
Original source: `.agents/skills/regular_web_daily_brief/SKILL.md`
Skill class: `regular`

This is a **wrapper** skill for `90_System/Skills/Web_Daily_Brief/`.

## Run
- Apply the Daily News block:
  - `.\.venv\Scripts\python.exe 90_System\Skills\Web_Daily_Brief\web_daily_brief.py apply --content-file 70_Exports\daily_news.md`
