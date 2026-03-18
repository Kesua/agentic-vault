#!/usr/bin/env bash
# Build a sanitized distribution ZIP of the Agentic Vault template.
# Mirrors the logic of 90_System/Skills/export_agentic_vault_template.ps1
# and adds the _setup/ wizard + bootstrap scripts.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGING="$REPO_ROOT/dist/agentic-vault"
ZIP_PATH="$REPO_ROOT/dist/agentic-vault.zip"

rm -rf "$STAGING" "$ZIP_PATH"

# ── Helpers ──────────────────────────────────────────────────────────

copy_tree_filtered() {
    local src="$1" dst="$2"
    shift 2
    local -a extensions=()
    local -a excludes=("__pycache__" "/runtime/" "/secrets/" "/Logs/")

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --ext) shift; IFS=',' read -ra extensions <<< "$1" ;;
        esac
        shift
    done

    [[ -d "$src" ]] || return 0
    mkdir -p "$dst"

    while IFS= read -r -d '' file; do
        local skip=false
        for exc in "${excludes[@]}"; do
            if [[ "$file" == *"$exc"* ]]; then skip=true; break; fi
        done
        [[ "$skip" == "true" ]] && continue

        if [[ ${#extensions[@]} -gt 0 ]]; then
            local ext=".${file##*.}"
            local match=false
            for e in "${extensions[@]}"; do
                if [[ "$ext" == "$e" ]]; then match=true; break; fi
            done
            [[ "$match" == "false" ]] && continue
        fi

        local rel="${file#"$src"/}"
        mkdir -p "$dst/$(dirname "$rel")"
        cp "$file" "$dst/$rel"
    done < <(find "$src" -type f -print0)
}

copy_file() {
    local rel="$1"
    local dst_rel="${2:-$rel}"
    local src="$REPO_ROOT/$rel"
    local dst="$STAGING/$dst_rel"
    if [[ -f "$src" ]]; then
        mkdir -p "$(dirname "$dst")"
        cp "$src" "$dst"
    else
        echo "  SKIP (not found): $rel"
    fi
}

# ── Filtered trees (matches export_agentic_vault_template.ps1) ──────

echo "Copying filtered trees..."
copy_tree_filtered "$REPO_ROOT/.agents"                                  "$STAGING/.agents"
copy_tree_filtered "$REPO_ROOT/.claude/hooks"                            "$STAGING/.claude/hooks"   --ext ".py"
copy_tree_filtered "$REPO_ROOT/.claude/skills"                           "$STAGING/.claude/skills"
copy_tree_filtered "$REPO_ROOT/90_System/Skills"                         "$STAGING/90_System/Skills" --ext ".md,.py,.ps1"
copy_tree_filtered "$REPO_ROOT/90_System/Integrations/Documentation"     "$STAGING/90_System/Integrations/Documentation" --ext ".md"

# ── Setup wizard and bootstrap scripts (new) ─────────────────────────

echo "Copying setup wizard..."
copy_tree_filtered "$REPO_ROOT/_setup" "$STAGING/_setup"
copy_file "Setup_Windows.bat"
copy_file "Setup_Mac.command"

# ── Individual integration files ─────────────────────────────────────

echo "Copying integration files..."
copy_file "90_System/Integrations/telegram_bridge/README.md"
copy_file "90_System/Integrations/telegram_bridge/run_telegram_bridge.ps1"
copy_file "90_System/Integrations/telegram_bridge/start_telegram_bridge.ps1"
copy_file "90_System/Integrations/telegram_bridge/stop_telegram_bridge.ps1"
copy_file "90_System/Integrations/telegram_bridge/telegram_bridge.py"
copy_file "90_System/Integrations/slack/app_info.txt"
copy_file "90_System/Integrations/slack/app_manifest.readonly.yaml"
copy_file "90_System/Integrations/slack/app_manifest.writefuture.yaml"
copy_file "90_System/TaskQueue/README.md"
copy_file "90_System/TaskQueue/Templates/Task_TEMPLATE.md"

# ── Root-level files ─────────────────────────────────────────────────

echo "Copying root files..."
copy_file ".gitignore"
copy_file "requirements.txt"
copy_file "how to initialize.md"
copy_file "AGENTS.md"
copy_file "SOUL.md"
copy_file "MEMORY.md"
copy_file "CLAUDE.md"
copy_file "SKILLS.md"
copy_file "README.md"
copy_file "AgentPrompts.md"

# ── Templates ────────────────────────────────────────────────────────

echo "Copying templates..."
copy_file "00_Mailbox/Templates/EmailSummary_TEMPLATE.md"
copy_file "00_Mailbox/Templates/EmailThread_TEMPLATE.md"
copy_file "00_Mailbox/Templates/SlackSummary_TEMPLATE.md"
copy_file "00_Mailbox/Templates/SlackThread_TEMPLATE.md"
copy_file "20_Meetings/Templates/MeetingNote_TEMPLATE.md"
copy_file "30_Projects/Templates/ProjectSnapshot_TEMPLATE.md"
copy_file "40_People/Templates/person_TEMPLATE.md"
copy_file "50_Areas/Area_TEMPLATE.md"
copy_file "60_SOPs/Templates/DailyBrief_TEMPLATE.md"
copy_file "60_SOPs/Templates/EmailThread_TEMPLATE.md"
copy_file "60_SOPs/Templates/WeeklyReview_TEMPLATE.md"

# ── SOP and index files ──────────────────────────────────────────────

echo "Copying SOPs and indexes..."
copy_file "60_SOPs/StartHere.md"
copy_file "60_SOPs/_HowIWork.md"
copy_file "60_SOPs/_AgentGuide.md"
copy_file "00_Mailbox/_Mailbox.md"
copy_file "20_Meetings/_MeetingIndex.md"
copy_file "30_Projects/_Projects.md"
copy_file "40_People/_PeopleIndex.md"
copy_file "50_Areas/_Areas.md"
copy_file ".codex/rules/vault.rules"

# ── Generated config files (generic, no personal paths) ─────────────

echo "Generating config files..."

mkdir -p "$STAGING/.codex"
cat > "$STAGING/.codex/config.toml" << 'TOML'
model = "gpt-5.4"

approval_policy = "on-request"
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true

# Uncomment and update the path below to your local vault location.
# allowed_roots = ["C:\\Users\\YourName\\path\\to\\agentic-vault"]
TOML

cat > "$STAGING/.codex/file_access_policy.toml" << 'TOML'
[read]
allow = ["**/*"]
deny  = [".git/**", ".venv/**", "90_System/secrets/**"]

[edit]
allow = [
  "**/*.md", "**/*.toml", "**/*.rules",
  "**/*.py", "**/*.ps1",
  "requirements.txt", ".gitignore",
]
deny  = [".git/**", ".venv/**", ".obsidian/**", "_attachments/**"]

[delete]
allow = []
deny  = ["**/*"]
TOML

cat > "$STAGING/.codex/README.md" << 'MD'
# Codex setup (repo-local)

Includes repo-local Codex configuration, command-approval rules, and wrapper skills.

Adjust `.codex/config.toml` for your local machine and any approved external repos.
MD

mkdir -p "$STAGING/.claude"
cat > "$STAGING/.claude/settings.json" << 'JSON'
{
  "permissions": {
    "allow": [
      "Bash(git status*)",
      "Bash(git diff*)",
      "Bash(git log*)",
      "Bash(git show*)",
      "Bash(git rev-parse*)",
      "Bash(git ls-files*)"
    ],
    "deny": [
      "Read(.git/**)",
      "Read(.venv/**)",
      "Read(.obsidian/**)",
      "Read(_attachments/**)",
      "Read(90_System/secrets/**)",
      "Read(**/.env)",
      "Read(**/.env.*)",
      "Edit(.git/**)",
      "Edit(.venv/**)",
      "Edit(.obsidian/**)",
      "Edit(_attachments/**)",
      "Edit(90_System/secrets/**)",
      "Write(.git/**)",
      "Write(.venv/**)",
      "Write(.obsidian/**)",
      "Write(_attachments/**)",
      "Write(90_System/secrets/**)",
      "MultiEdit(.git/**)",
      "MultiEdit(.venv/**)",
      "MultiEdit(.obsidian/**)",
      "MultiEdit(_attachments/**)",
      "MultiEdit(90_System/secrets/**)"
    ]
  }
}
JSON

cat > "$STAGING/.claude/settings.local.example.json" << 'JSON'
{
  "additionalDirectories": []
}
JSON

cat > "$STAGING/.claude/README.md" << 'MD'
# Claude setup (repo-local)

Includes mirrored Claude-facing skills, hooks, and settings.
Keep machine-specific access in your user-level Claude settings.
MD

# ── Empty content directories ────────────────────────────────────────

echo "Creating directory structure..."

for dir in \
    "90_System/TaskQueue/pending" \
    "90_System/TaskQueue/running" \
    "90_System/TaskQueue/failed" \
    "90_System/TaskQueue/done" \
    "90_System/secrets" \
    "10_DailyBriefs" \
    "20_Meetings" \
    "30_Projects" \
    "40_People" \
    "50_Areas" \
    "70_Exports" \
    "_attachments"; do
    mkdir -p "$STAGING/$dir"
done

for dir in \
    "90_System/TaskQueue/pending" \
    "90_System/TaskQueue/running" \
    "90_System/TaskQueue/failed" \
    "90_System/TaskQueue/done"; do
    touch "$STAGING/$dir/.gitkeep"
done

# ── File permissions for Mac ─────────────────────────────────────────

echo "Setting file permissions..."
[[ -f "$STAGING/Setup_Mac.command" ]]        && chmod +x "$STAGING/Setup_Mac.command"
[[ -f "$STAGING/_setup/bootstrap_mac.sh" ]]  && chmod +x "$STAGING/_setup/bootstrap_mac.sh"

# ── Create ZIP ───────────────────────────────────────────────────────

echo "Creating ZIP..."
mkdir -p "$REPO_ROOT/dist"
(cd "$REPO_ROOT/dist" && zip -qr "agentic-vault.zip" "agentic-vault/")

ZIP_SIZE=$(du -h "$ZIP_PATH" | cut -f1)
echo ""
echo "Done: dist/agentic-vault.zip ($ZIP_SIZE)"
