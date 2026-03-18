---
name: "adhoc-bridge-start"
description: "Wrapper skill: start the local Telegram bridge in the background with a deterministic script."
---

# Ad-hoc Bridge Start

This is a Claude Code mirror of `adhoc_bridge_Start` from `.agents/skills/`.
Original source: `.agents/skills/adhoc_bridge_Start/SKILL.md`
Skill class: `adhoc`

Use this when the user wants the local Telegram bridge started without remembering the command.

## What it does
- Validates the bridge Python path and local config file
- Starts the Telegram bridge in the background
- Writes the running process ID to `90_System\Integrations\telegram_bridge\runtime\bridge.pid`
- Returns success if the bridge is already running with the recorded PID

## Run
- Start bridge:
  - Execute outside the sandbox.
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Integrations\telegram_bridge\start_telegram_bridge.ps1`

## Notes
- This skill is local-machine only.
- Always request escalated execution for this wrapper so the background process survives after the command returns.
- Use `adhoc_bridge_end` to stop the same background process cleanly.
