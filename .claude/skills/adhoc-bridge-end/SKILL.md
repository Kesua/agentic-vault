---
name: "adhoc-bridge-end"
description: "Wrapper skill: stop the local Telegram bridge background process using the recorded PID."
---

# Ad-hoc Bridge End

This is a Claude Code mirror of `adhoc_bridge_end` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_bridge_end/SKILL.md`
Skill class: `adhoc`

Use this when the user wants the local Telegram bridge stopped without remembering the command.

## What it does
- Reads `90_System\Integrations\telegram_bridge\runtime\bridge.pid`
- Stops the recorded bridge process if it is still running
- Removes stale PID files when the recorded process is already gone

## Run
- Stop bridge:
  - Execute outside the sandbox.
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Integrations\telegram_bridge\stop_telegram_bridge.ps1`

## Notes
- This skill is local-machine only.
- Always request escalated execution for this wrapper so it can reliably stop the persisted background process.
- If the PID file is missing, the skill reports that the bridge is likely not running.
