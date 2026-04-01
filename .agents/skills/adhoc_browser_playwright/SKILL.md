---
name: "adhoc_browser_playwright"
description: "Wrapper skill: use the global Playwright Browser plugin for browser-first web tasks such as DOM inspection, screenshots, response capture, lazy-loaded galleries, and controlled interactive website workflows."
---

# Ad-hoc Browser Playwright

This is a **wrapper** skill for the global Playwright Browser plugin and the vault guidance in `90_System/Skills/browser_playwright/`.

## Scope
- Open and use a real browser session
- Navigate websites that block plain HTTP clients
- Inspect DOM text or HTML
- Capture screenshots
- Capture network responses and save response bodies
- Perform controlled click/type/press interaction when the task explicitly requires it

## Rules
- Default to read-first browser behavior
- Use browser evidence before making claims about dynamic pages
- Save browser-generated files only into approved vault export paths
- Close sessions when the task is done

## Reference
- Full docs: `90_System/Skills/browser_playwright/SKILL.md`
