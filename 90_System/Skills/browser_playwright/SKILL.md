---
name: "browser-playwright"
description: "Use the global Playwright Browser plugin for real browser automation, DOM inspection, screenshots, and response capture. Trigger when Codex needs a real browser session, browser-backed asset downloads, lazy-loaded page traversal, or controlled click/type workflows that plain HTTP fetch cannot handle."
---

# Playwright Browser

This skill documents the repo-local policy layer for the global `playwright-browser` plugin.

## Purpose
- Use a real Chromium browser session via MCP.
- Prefer browser-backed navigation and evidence capture over raw HTTP guessing.
- Support both general web tasks and browser-gated fetch workflows like Sreality galleries.

## Read-First policy
- Default to read-only browser behavior:
  - open session
  - navigate
  - inspect DOM
  - capture screenshots
  - capture network responses
- Only click, type, or press keys when the user task explicitly requires interaction.
- Do not submit destructive actions, purchases, deletes, publishes, or account changes unless the user asks for that exact action.

## Expected workflow
1. Open a browser session.
2. Navigate to the target URL.
3. Read page text or HTML before making claims.
4. If the site lazy-loads data or images, walk the UI and capture relevant network responses.
5. Save artifacts only to approved vault paths when the task requires local files.
6. Close the browser session when done.

## Artifact paths in this vault
- For project-local exploratory browser artifacts, prefer the project's `export/` folder.
- For non-project or external-file workflows, export under `70_Exports/YYYY/MM/DD/`.

## Installation / repair
- Install or refresh the global plugin on Windows with:
  - `powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\Skills\browser_playwright\install_playwright_browser_plugin.ps1`
- Install or refresh the global plugin on macOS with:
  - `bash 90_System/Skills/browser_playwright/install_playwright_browser_plugin.sh`

## Notes
- The global plugin lives outside the vault as a local Codex plugin and is registered via the home marketplace.
- The plugin exposes MCP tools like session open/close, navigate, query, screenshot, and response download.
