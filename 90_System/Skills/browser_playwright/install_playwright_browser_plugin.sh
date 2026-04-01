#!/usr/bin/env bash

set -euo pipefail

PLUGIN_ROOT="$HOME/plugins/playwright-browser"
SERVER_PATH="$PLUGIN_ROOT/scripts/server.mjs"
SKILL_PATH="$PLUGIN_ROOT/skills/playwright-browser-use/SKILL.md"
PLUGIN_JSON_PATH="$PLUGIN_ROOT/.codex-plugin/plugin.json"
MCP_PATH="$PLUGIN_ROOT/.mcp.json"
PACKAGE_JSON_PATH="$PLUGIN_ROOT/package.json"
MARKETPLACE_PATH="$HOME/.agents/plugins/marketplace.json"

write_utf8_no_bom() {
  local target_path="$1"
  local content="$2"
  mkdir -p "$(dirname "$target_path")"
  printf '%s' "$content" > "$target_path"
}

ensure_node() {
  if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 && command -v npx >/dev/null 2>&1; then
    return 0
  fi

  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew is required to install Node.js for Playwright Browser on macOS." >&2
    exit 1
  fi

  brew install node
}

ensure_node

PLUGIN_JSON_CONTENT=$(cat <<'EOF'
{
  "name": "playwright-browser",
  "version": "0.1.0",
  "description": "General-purpose Playwright browser automation plugin for Codex with persistent browser sessions, DOM inspection, screenshots, and network response capture.",
  "author": {
    "name": "Jan Papousek",
    "email": "jan.papousek@weareflo.com",
    "url": "https://playwright.dev/"
  },
  "homepage": "https://playwright.dev/docs/intro",
  "repository": "https://playwright.dev/docs/intro",
  "license": "MIT",
  "keywords": [
    "playwright",
    "browser",
    "mcp",
    "automation",
    "web"
  ],
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "interface": {
    "displayName": "Playwright Browser",
    "shortDescription": "Use a real browser session for reading and controlled interaction on the web.",
    "longDescription": "Open real Chromium browser sessions from Codex, navigate pages, inspect DOM, take screenshots, capture network responses, and run controlled interactive web tasks via Playwright.",
    "developerName": "Jan Papousek",
    "category": "Productivity",
    "capabilities": [
      "Interactive",
      "Read",
      "Write"
    ],
    "websiteURL": "https://playwright.dev/docs/intro",
    "privacyPolicyURL": "https://playwright.dev/docs/intro",
    "termsOfServiceURL": "https://playwright.dev/docs/intro",
    "defaultPrompt": [
      "Open a real browser and inspect this page.",
      "Capture screenshots and extract the DOM from this site.",
      "Use Playwright to walk through this web workflow."
    ],
    "brandColor": "#45BA63"
  }
}
EOF
)
write_utf8_no_bom "$PLUGIN_JSON_PATH" "$PLUGIN_JSON_CONTENT"

PACKAGE_JSON_CONTENT=$(cat <<'EOF'
{
  "name": "playwright-browser",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "start": "node ./scripts/server.mjs",
    "check": "node --check ./scripts/server.mjs"
  },
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.11.0",
    "playwright": "^1.53.0"
  }
}
EOF
)
write_utf8_no_bom "$PACKAGE_JSON_PATH" "$PACKAGE_JSON_CONTENT"

MCP_JSON_CONTENT=$(cat <<EOF
{
  "mcpServers": {
    "playwright-browser": {
      "command": "node",
      "args": [
        "$SERVER_PATH"
      ]
    }
  }
}
EOF
)
write_utf8_no_bom "$MCP_PATH" "$MCP_JSON_CONTENT"

SKILL_CONTENT=$(cat <<'EOF'
---
name: playwright-browser-use
description: Use the Playwright Browser plugin when Codex needs a real browser session for navigation, DOM inspection, screenshots, response capture, gallery walking, or controlled web interaction on sites where plain HTTP fetch is insufficient.
---

# Playwright Browser Use

Use the Playwright Browser plugin for browser-first web tasks.

## Default workflow
- Open a browser session.
- Navigate to the target page.
- Read DOM text or HTML before making claims.
- Capture screenshots or network responses when page evidence matters.
- Use click/type/press only when the task explicitly requires interaction.

## Safety
- Default to read-first behavior.
- Treat login, form submit, purchases, publishing, deletion, or account changes as explicit-action steps only.
- Prefer screenshots, DOM extraction, and response capture over guessing from partial HTML.

## Good fits
- Websites that block raw HTTP clients.
- Pages that lazy-load galleries or data.
- Tasks that need browser state, cookies, or session-backed downloads.
- Visual verification tasks.

## Core tools
- `browser_open_session`
- `browser_navigate`
- `browser_get_page`
- `browser_query`
- `browser_click`
- `browser_type`
- `browser_press`
- `browser_wait_for`
- `browser_screenshot`
- `browser_list_network`
- `browser_download_response`
- `browser_close_session`
EOF
)
write_utf8_no_bom "$SKILL_PATH" "$SKILL_CONTENT"

SERVER_SOURCE=$(cat <<'EOF'
import { randomUUID } from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "playwright";
import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { CallToolRequestSchema, ListToolsRequestSchema } from "@modelcontextprotocol/sdk/types.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const pluginRoot = path.resolve(__dirname, "..");
const runtimeRoot = path.join(pluginRoot, "runtime");
const sessions = new Map();

async function ensureDir(dir) {
  await fs.mkdir(dir, { recursive: true });
  return dir;
}

function nowStamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function jsonResult(payload) {
  return {
    content: [
      {
        type: "text",
        text: JSON.stringify(payload, null, 2),
      },
    ],
  };
}

function getSession(sessionId) {
  const session = sessions.get(sessionId);
  if (!session) {
    throw new Error(`Unknown session_id '${sessionId}'.`);
  }
  return session;
}

function sanitizeFilename(input) {
  return String(input || "artifact")
    .replace(/[^a-zA-Z0-9._-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "") || "artifact";
}

function inferExtension(urlString, contentType) {
  try {
    const pathname = new URL(urlString).pathname;
    const ext = path.extname(pathname);
    if (ext) return ext;
  } catch {}
  if (!contentType) return ".bin";
  if (contentType.includes("png")) return ".png";
  if (contentType.includes("jpeg") || contentType.includes("jpg")) return ".jpg";
  if (contentType.includes("webp")) return ".webp";
  if (contentType.includes("gif")) return ".gif";
  if (contentType.includes("json")) return ".json";
  if (contentType.includes("html")) return ".html";
  if (contentType.includes("svg")) return ".svg";
  return ".bin";
}

function trimText(text, limit = 20000) {
  if (!text) return "";
  return text.length > limit ? `${text.slice(0, limit)}\n...[truncated]` : text;
}

function pickResponses(session, filters = {}) {
  const { host_contains, url_contains, content_type_contains } = filters;
  return session.responses.filter((entry) => {
    if (host_contains && !(entry.host || "").includes(host_contains)) return false;
    if (url_contains && !entry.url.includes(url_contains)) return false;
    if (content_type_contains && !(entry.contentType || "").includes(content_type_contains)) return false;
    return true;
  });
}

async function attachPage(session, page) {
  session.page = page;
  page.on("response", (response) => {
    const request = response.request();
    const headers = response.headers();
    const contentType = headers["content-type"] || "";
    let host = "";
    try {
      host = new URL(response.url()).host;
    } catch {}
    session.responses.push({
      id: randomUUID(),
      response,
      pageUrl: page.url(),
      url: response.url(),
      host,
      status: response.status(),
      method: request.method(),
      resourceType: request.resourceType(),
      contentType,
      capturedAt: new Date().toISOString(),
    });
  });
}

async function openSession(args = {}) {
  const headless = args.headless ?? false;
  const profileName = sanitizeFilename(args.profile_name || "default");
  const sessionId = randomUUID();
  const profileDir = await ensureDir(path.join(runtimeRoot, "profiles", profileName));
  const artifactsDir = await ensureDir(path.join(runtimeRoot, "artifacts", sessionId));
  const context = await chromium.launchPersistentContext(profileDir, {
    headless,
    viewport: args.viewport_width && args.viewport_height
      ? { width: Number(args.viewport_width), height: Number(args.viewport_height) }
      : undefined,
    acceptDownloads: true,
  });
  const page = context.pages()[0] || await context.newPage();
  const session = {
    id: sessionId,
    profileName,
    profileDir,
    artifactsDir,
    context,
    page,
    responses: [],
    createdAt: new Date().toISOString(),
  };
  context.on("page", async (newPage) => {
    await attachPage(session, newPage);
  });
  await attachPage(session, page);
  sessions.set(sessionId, session);
  return {
    session_id: sessionId,
    profile_name: profileName,
    headless,
    artifacts_dir: artifactsDir,
    profile_dir: profileDir,
  };
}

async function navigate(args) {
  const session = getSession(args.session_id);
  const response = await session.page.goto(args.url, {
    waitUntil: args.wait_until || "load",
    timeout: Number(args.timeout_ms || 30000),
  });
  return {
    session_id: session.id,
    url: session.page.url(),
    title: await session.page.title(),
    status: response?.status() ?? null,
  };
}

async function getPage(args) {
  const session = getSession(args.session_id);
  const includeHtml = Boolean(args.include_html);
  const textLimit = Number(args.text_limit || 20000);
  const bodyText = await session.page.evaluate(() => document.body?.innerText || "");
  const result = {
    session_id: session.id,
    url: session.page.url(),
    title: await session.page.title(),
    text: trimText(bodyText, textLimit),
  };
  if (includeHtml) {
    result.html = await session.page.content();
  }
  return result;
}

async function query(args) {
  const session = getSession(args.session_id);
  const limit = Number(args.limit || 20);
  const selector = String(args.selector);
  const all = Boolean(args.all);
  const includeHtml = Boolean(args.include_html);
  const includeAttributes = Boolean(args.include_attributes);
  const attributeNames = Array.isArray(args.attribute_names) ? args.attribute_names : [];
  const payload = await session.page.$$eval(
    selector,
    (elements, queryArgs) => {
      const chosen = (queryArgs.all ? elements : elements.slice(0, 1)).slice(0, queryArgs.limit);
      return chosen.map((node, index) => {
        const item = {
          index,
          text: (node.innerText ?? node.textContent ?? "").trim(),
        };
        if (queryArgs.includeHtml) item.html = node.outerHTML;
        if (queryArgs.includeAttributes) {
          if (queryArgs.attributeNames.length === 0) {
            item.attributes = Object.fromEntries(Array.from(node.attributes).map((attr) => [attr.name, attr.value]));
          } else {
            item.attributes = Object.fromEntries(queryArgs.attributeNames.map((name) => [name, node.getAttribute(name)]));
          }
        }
        return item;
      });
    },
    { all, limit, includeHtml, includeAttributes, attributeNames }
  );
  return {
    session_id: session.id,
    selector,
    count: payload.length,
    items: payload,
  };
}

async function click(args) {
  const session = getSession(args.session_id);
  await session.page.click(args.selector, {
    button: args.button || "left",
    clickCount: Number(args.click_count || 1),
    timeout: Number(args.timeout_ms || 10000),
  });
  if (args.wait_after_ms) {
    await session.page.waitForTimeout(Number(args.wait_after_ms));
  }
  return {
    session_id: session.id,
    url: session.page.url(),
    title: await session.page.title(),
    clicked: args.selector,
  };
}

async function typeText(args) {
  const session = getSession(args.session_id);
  if (args.clear ?? true) {
    await session.page.fill(args.selector, "", { timeout: Number(args.timeout_ms || 10000) });
  }
  await session.page.fill(args.selector, String(args.text ?? ""), { timeout: Number(args.timeout_ms || 10000) });
  return {
    session_id: session.id,
    typed_into: args.selector,
    characters: String(args.text ?? "").length,
  };
}

async function pressKey(args) {
  const session = getSession(args.session_id);
  await session.page.press(args.selector, args.key, { timeout: Number(args.timeout_ms || 10000) });
  return {
    session_id: session.id,
    selector: args.selector,
    key: args.key,
  };
}

async function waitFor(args) {
  const session = getSession(args.session_id);
  await session.page.waitForSelector(args.selector, {
    state: args.state || "visible",
    timeout: Number(args.timeout_ms || 10000),
  });
  return {
    session_id: session.id,
    selector: args.selector,
    state: args.state || "visible",
  };
}

async function screenshot(args) {
  const session = getSession(args.session_id);
  const explicitPath = args.path;
  const filePath = explicitPath || path.join(session.artifactsDir, `${nowStamp()}-${sanitizeFilename(args.name || "screenshot")}.png`);
  await ensureDir(path.dirname(filePath));
  await session.page.screenshot({
    path: filePath,
    fullPage: args.full_page ?? true,
  });
  return {
    session_id: session.id,
    path: filePath,
    url: session.page.url(),
  };
}

async function listNetwork(args) {
  const session = getSession(args.session_id);
  const limit = Number(args.limit || 50);
  const matches = pickResponses(session, args).slice(-limit).map((entry) => ({
    id: entry.id,
    url: entry.url,
    host: entry.host,
    status: entry.status,
    method: entry.method,
    resource_type: entry.resourceType,
    content_type: entry.contentType,
    captured_at: entry.capturedAt,
    page_url: entry.pageUrl,
  }));
  return {
    session_id: session.id,
    count: matches.length,
    items: matches,
  };
}

async function downloadResponse(args) {
  const session = getSession(args.session_id);
  let entry = null;
  if (args.response_id) {
    entry = session.responses.find((candidate) => candidate.id === args.response_id) || null;
  } else {
    entry = pickResponses(session, args)[0] || null;
  }
  if (!entry) {
    throw new Error("No matching response found to download.");
  }
  const body = await entry.response.body();
  const ext = inferExtension(entry.url, entry.contentType);
  const outputDir = await ensureDir(args.output_dir || session.artifactsDir);
  const baseName = sanitizeFilename(args.filename || `${nowStamp()}-${entry.host || "response"}`);
  const outputPath = path.join(outputDir, `${baseName}${ext}`);
  await fs.writeFile(outputPath, body);
  return {
    session_id: session.id,
    response_id: entry.id,
    url: entry.url,
    content_type: entry.contentType,
    path: outputPath,
    size_bytes: body.length,
  };
}

async function closeSession(args) {
  const session = getSession(args.session_id);
  await session.context.close();
  sessions.delete(session.id);
  return {
    session_id: session.id,
    closed: true,
  };
}

const tools = [
  {
    name: "browser_open_session",
    description: "Open a real Chromium browser session with a persistent profile.",
    inputSchema: {
      type: "object",
      properties: {
        profile_name: { type: "string" },
        headless: { type: "boolean" },
        viewport_width: { type: "number" },
        viewport_height: { type: "number" }
      }
    }
  },
  {
    name: "browser_navigate",
    description: "Navigate the active page in a browser session.",
    inputSchema: {
      type: "object",
      required: ["session_id", "url"],
      properties: {
        session_id: { type: "string" },
        url: { type: "string" },
        wait_until: { type: "string" },
        timeout_ms: { type: "number" }
      }
    }
  },
  {
    name: "browser_get_page",
    description: "Return title, URL, visible text, and optional HTML for the current page.",
    inputSchema: {
      type: "object",
      required: ["session_id"],
      properties: {
        session_id: { type: "string" },
        include_html: { type: "boolean" },
        text_limit: { type: "number" }
      }
    }
  },
  {
    name: "browser_query",
    description: "Query one or more DOM elements by CSS selector and return text plus optional HTML or attributes.",
    inputSchema: {
      type: "object",
      required: ["session_id", "selector"],
      properties: {
        session_id: { type: "string" },
        selector: { type: "string" },
        all: { type: "boolean" },
        limit: { type: "number" },
        include_html: { type: "boolean" },
        include_attributes: { type: "boolean" },
        attribute_names: { type: "array", "items": { type: "string" } }
      }
    }
  },
  {
    name: "browser_click",
    description: "Click an element in the current page.",
    inputSchema: {
      type: "object",
      required: ["session_id", "selector"],
      properties: {
        session_id: { type: "string" },
        selector: { type: "string" },
        button: { type: "string" },
        click_count: { type: "number" },
        timeout_ms: { type: "number" },
        wait_after_ms: { type: "number" }
      }
    }
  },
  {
    name: "browser_type",
    description: "Fill text into a form field.",
    inputSchema: {
      type: "object",
      required: ["session_id", "selector", "text"],
      properties: {
        session_id: { type: "string" },
        selector: { type: "string" },
        text: { type: "string" },
        clear: { type: "boolean" },
        timeout_ms: { type: "number" }
      }
    }
  },
  {
    name: "browser_press",
    description: "Press a keyboard key on a target element.",
    inputSchema: {
      type: "object",
      required: ["session_id", "selector", "key"],
      properties: {
        session_id: { type: "string" },
        selector: { type: "string" },
        key: { type: "string" },
        timeout_ms: { type: "number" }
      }
    }
  },
  {
    name: "browser_wait_for",
    description: "Wait for an element to reach a state like visible or attached.",
    inputSchema: {
      type: "object",
      required: ["session_id", "selector"],
      properties: {
        session_id: { type: "string" },
        selector: { type: "string" },
        state: { type: "string" },
        timeout_ms: { type: "number" }
      }
    }
  },
  {
    name: "browser_screenshot",
    description: "Capture a screenshot of the current page.",
    inputSchema: {
      type: "object",
      required: ["session_id"],
      properties: {
        session_id: { type: "string" },
        full_page: { type: "boolean" },
        name: { type: "string" },
        path: { type: "string" }
      }
    }
  },
  {
    name: "browser_list_network",
    description: "List captured network responses for the current session.",
    inputSchema: {
      type: "object",
      required: ["session_id"],
      properties: {
        session_id: { type: "string" },
        host_contains: { type: "string" },
        url_contains: { type: "string" },
        content_type_contains: { type: "string" },
        limit: { type: "number" }
      }
    }
  },
  {
    name: "browser_download_response",
    description: "Save a captured network response body to disk.",
    inputSchema: {
      type: "object",
      required: ["session_id"],
      properties: {
        session_id: { type: "string" },
        response_id: { type: "string" },
        host_contains: { type: "string" },
        url_contains: { type: "string" },
        content_type_contains: { type: "string" },
        output_dir: { type: "string" },
        filename: { type: "string" }
      }
    }
  },
  {
    name: "browser_close_session",
    description: "Close a browser session and release its resources.",
    inputSchema: {
      type: "object",
      required: ["session_id"],
      properties: {
        session_id: { type: "string" }
      }
    }
  }
];

const server = new Server(
  { name: "playwright-browser", version: "0.1.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools }));
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args = {} } = request.params;
  try {
    switch (name) {
      case "browser_open_session":
        return jsonResult(await openSession(args));
      case "browser_navigate":
        return jsonResult(await navigate(args));
      case "browser_get_page":
        return jsonResult(await getPage(args));
      case "browser_query":
        return jsonResult(await query(args));
      case "browser_click":
        return jsonResult(await click(args));
      case "browser_type":
        return jsonResult(await typeText(args));
      case "browser_press":
        return jsonResult(await pressKey(args));
      case "browser_wait_for":
        return jsonResult(await waitFor(args));
      case "browser_screenshot":
        return jsonResult(await screenshot(args));
      case "browser_list_network":
        return jsonResult(await listNetwork(args));
      case "browser_download_response":
        return jsonResult(await downloadResponse(args));
      case "browser_close_session":
        return jsonResult(await closeSession(args));
      default:
        throw new Error(`Unknown tool '${name}'.`);
    }
  } catch (error) {
    return {
      content: [
        {
          type: "text",
          text: JSON.stringify({ error: error instanceof Error ? error.message : String(error) }, null, 2),
        },
      ],
      isError: true,
    };
  }
});

async function main() {
  await ensureDir(runtimeRoot);
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error);
    process.exit(1);
  });
}
EOF
)
write_utf8_no_bom "$SERVER_PATH" "$SERVER_SOURCE"

mkdir -p "$(dirname "$MARKETPLACE_PATH")"
if [[ -f "$MARKETPLACE_PATH" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    python3 - <<'PY' "$MARKETPLACE_PATH"
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text(encoding="utf-8"))
data["name"] = "jan-local-plugins"
interface = data.setdefault("interface", {})
interface["displayName"] = "Jan Local Plugins"
path.write_text(json.dumps(data, indent=2, ensure_ascii=True), encoding="utf-8")
PY
  else
    echo "python3 is required to update the plugin marketplace metadata." >&2
    exit 1
  fi
else
  MARKETPLACE_CONTENT=$(cat <<'EOF'
{
  "name": "jan-local-plugins",
  "interface": {
    "displayName": "Jan Local Plugins"
  },
  "plugins": []
}
EOF
)
  write_utf8_no_bom "$MARKETPLACE_PATH" "$MARKETPLACE_CONTENT"
fi

cd "$PLUGIN_ROOT"
npm install
npx playwright install chromium
npm run check
node -e "import('./scripts/server.mjs').then(() => console.log('module-import-ok')).catch(err => { console.error(err); process.exit(1); })"
