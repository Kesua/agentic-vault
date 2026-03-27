from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
SOURCE_SKILLS_DIR = REPO_ROOT / ".agents" / "skills"
CLAUDE_DIR = REPO_ROOT / ".claude"
CLAUDE_SKILLS_DIR = CLAUDE_DIR / "skills"
CLAUDE_HOOKS_DIR = CLAUDE_DIR / "hooks"

SHARED_DENY_READ_GLOBS = [
    ".git/**",
    ".venv/**",
    ".obsidian/**",
    "_attachments/**",
    "OneNoteNotes/**",
    "90_System/secrets/**",
    "**/.env",
    "**/.env.*",
]

SHARED_DENY_EDIT_GLOBS = [
    ".git/**",
    ".venv/**",
    ".obsidian/**",
    "_attachments/**",
    "OneNoteNotes/**",
    "90_System/secrets/**",
]

BASH_ALLOWLIST = [
    "git status",
    "git diff",
    "git log",
    "git show",
    "git rev-parse",
    "git ls-files",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\gcal_today\\gcal_today.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\daily_brief_todoist\\daily_brief_todoist.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\fireflies_sync\\fireflies_sync.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\create_links\\create_links.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\Web_Daily_Brief\\web_daily_brief.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\git_submodules_pull\\git_submodules_pull.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\process_emails\\process_emails.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\process_slack\\process_slack.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\meeting_attendees_people_sync\\attendee_people_sync.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\gmail_assistant\\gmail_assistant.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\adhoc_gcal\\adhoc_gcal.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\adhoc_todoist\\adhoc_todoist.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\adhoc_fireflies\\adhoc_fireflies.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\clockify_sync\\adhoc_clockify.py",
    ".\\.venv\\Scripts\\python.exe 90_System\\Skills\\files_search\\files_search.py",
    "powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Skills\\git_submodules_pull\\git_submodules_pull.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\start_telegram_bridge.ps1",
    "powershell -NoProfile -ExecutionPolicy Bypass -File 90_System\\Integrations\\telegram_bridge\\stop_telegram_bridge.ps1",
]

CLAUDE_README = """# Claude Code setup (repo-local)

This repo keeps Codex-facing docs and wrappers as the source of truth and generates a Claude Code mirror from them.

## Generated files
- `CLAUDE.md`
- `.claude/settings.json`
- `.claude/hooks/`
- `.claude/skills/`
- `.claude/generated-map.json`

Regenerate after changing `AGENTS.md`, `SOUL.md`, `MEMORY.md`, `SKILLS.md`, or `.agents/skills/**`:

```powershell
.\\.venv\\Scripts\\python.exe 90_System\\Skills\\claude_code_mirror\\sync_claude_code.py
```

## Local setup
- Shared project rules live in `.claude/settings.json`.
- Put machine-specific access in `~/.claude/settings.json`.
- Put personal cross-project preferences in `~/.claude/CLAUDE.md`.

Suggested user settings:

```json
{
  "additionalDirectories": [
    "C:\\\\Users\\\\jan.papousek\\\\.codex\\\\memories",
    "C:\\\\Users\\\\jan.papousek\\\\OneDrive\\\\Dokumenty\\\\Business\\\\Invoicing"
  ]
}
```

## References
- Memory: https://code.claude.com/docs/en/memory
- Settings: https://code.claude.com/docs/en/settings
- Skills: https://code.claude.com/docs/en/skills
- Hooks: https://code.claude.com/docs/en/hooks
- Sub-agents: https://code.claude.com/docs/en/sub-agents
- MCP: https://code.claude.com/docs/en/mcp
"""

CLAUDE_SETTINGS_LOCAL_EXAMPLE = """{
  "additionalDirectories": [
    "C:\\\\Users\\\\jan.papousek\\\\.codex\\\\memories",
    "C:\\\\Users\\\\jan.papousek\\\\OneDrive\\\\Dokumenty\\\\Business\\\\Invoicing"
  ]
}
"""

PRE_TOOL_USE_SCRIPT = r"""from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EXPORT_ROOT = REPO_ROOT / "70_Exports"
BLOCKED_SEGMENTS = {
    ".git",
    ".venv",
    ".obsidian",
    "_attachments",
    "OneNoteNotes",
}
BLOCKED_PREFIXES = [
    REPO_ROOT / "90_System" / "secrets",
]


def _load_payload() -> dict:
    raw = sys.stdin.read().strip()
    return json.loads(raw) if raw else {}


def _collect_paths(tool_name: str, tool_input: dict) -> list[Path]:
    candidates: list[str] = []
    if tool_name == "Write":
        candidates.extend([tool_input.get("file_path"), tool_input.get("path")])
    elif tool_name in {"Edit", "MultiEdit"}:
        candidates.extend([tool_input.get("file_path"), tool_input.get("path")])
    return [Path(candidate) for candidate in candidates if candidate]


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except Exception:
        return False


def _is_external_source_edit(path: Path) -> bool:
    if _is_within(path, REPO_ROOT):
        return False
    if _is_within(path, EXPORT_ROOT):
        return False
    return bool(re.search(r"\.(docx|pdf|xlsx|csv|tsv)$", path.name, flags=re.IGNORECASE))


def _blocked_reason(path: Path) -> str | None:
    normalized = path.resolve()

    for prefix in BLOCKED_PREFIXES:
        if _is_within(normalized, prefix):
            return f"Blocked path: {path}"

    if _is_within(normalized, REPO_ROOT):
        rel = normalized.relative_to(REPO_ROOT.resolve())
        if rel.parts and rel.parts[0] in BLOCKED_SEGMENTS:
            return f"Blocked path: {path}"

    if _is_external_source_edit(normalized):
        return (
            "External source files must not be edited in place. "
            "Copy them under 70_Exports/YYYY/MM/DD/ and edit only the exported copy."
        )

    return None


def main() -> int:
    payload = _load_payload()
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {}) or {}

    for path in _collect_paths(tool_name, tool_input):
        reason = _blocked_reason(path)
        if reason:
            print(reason, file=sys.stderr)
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.rstrip() + "\n", encoding="utf-8")


def remove_tree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    if not markdown.startswith("---\n"):
        return {}, markdown.strip()

    _, frontmatter, body = markdown.split("---\n", 2)
    parsed: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"')
    return parsed, body.strip()


def parse_simple_yaml(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    parsed: dict[str, str] = {}
    for line in read_text(path).splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, value = stripped.split(":", 1)
        parsed[key.strip()] = value.strip().strip('"')
    return parsed


def extract_bullets(markdown: str, heading: str) -> list[str]:
    pattern = re.compile(
        rf"^#{{2,3}} {re.escape(heading)}\s*$([\s\S]*?)(?=^#{{2,3}} |\Z)",
        flags=re.MULTILINE,
    )
    match = pattern.search(markdown)
    if not match:
        return []

    bullets: list[str] = []
    for line in match.group(1).splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            bullets.append(stripped[2:])
    return bullets


def slugify(name: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-{2,}", "-", slug)


def split_title(body: str, fallback: str) -> tuple[str, str]:
    lines = body.strip().splitlines()
    if lines and lines[0].startswith("# "):
        return lines[0][2:].strip(), "\n".join(lines[1:]).strip()
    return fallback, body.strip()


def infer_skill_class(source_name: str) -> str:
    if source_name.startswith("regular_"):
        return "regular"
    if source_name.startswith("bulk_"):
        return "bulk"
    if source_name.startswith("adhoc_"):
        return "adhoc"
    return "general"


def build_claude_md() -> str:
    agents = read_text(REPO_ROOT / "AGENTS.md")
    soul = read_text(REPO_ROOT / "SOUL.md")
    memory = read_text(REPO_ROOT / "MEMORY.md")

    identity = extract_bullets(soul, "Identity")
    defaults = extract_bullets(soul, "Behavioral Defaults")
    non_negotiables = extract_bullets(agents, "Non-negotiables")
    session_bootstrap = extract_bullets(agents, "Session bootstrap")
    canonical_paths = extract_bullets(agents, "Canonical paths for locally stored data")
    file_naming = extract_bullets(agents, "File naming")
    add_content = extract_bullets(agents, "When adding new content")
    deliverables = extract_bullets(agents, "Agent deliverables")
    preferences = extract_bullets(memory, "Preferences")
    learned_rules = extract_bullets(memory, "Learned Rules")
    useful_pointers = extract_bullets(memory, "Useful Pointers")
    known_pitfalls = extract_bullets(memory, "Known Pitfalls")

    sections = [
        "# Claude Instructions (ChiefOfStuffVault)",
        "",
        "This file is generated from the repo-local Codex guidance. Treat the Codex docs as the source of truth and regenerate after changing them.",
        "",
        "## Vault identity",
    ]
    sections.extend(f"- {item}" for item in identity)
    sections.extend(
        [
            "",
            "## Startup",
            "- At the start of each session, read `AGENTS.md`, `SOUL.md`, and `MEMORY.md` from the repo root.",
        ]
    )
    sections.extend(
        f"- {item}"
        for item in session_bootstrap
        if item
        not in {
            "In every session, read this `AGENTS.md`, `SOUL.md` as a behavioral guidance and `MEMORY.md` as learned working memory from root."
        }
    )
    sections.extend(
        [
            "",
            "## Behavioral defaults",
        ]
    )
    sections.extend(f"- {item}" for item in defaults)
    sections.extend(f"- {item}" for item in preferences)
    sections.extend(
        [
            "",
            "## Non-negotiables",
        ]
    )
    sections.extend(f"- {item}" for item in non_negotiables)
    sections.extend(
        [
            "",
            "## Canonical paths",
        ]
    )
    sections.extend(f"- {item}" for item in canonical_paths)
    sections.extend(
        [
            "",
            "## Naming",
        ]
    )
    sections.extend(f"- {item}" for item in file_naming)
    sections.extend(
        [
            "",
            "## Follow-up updates",
        ]
    )
    sections.extend(f"- {item}" for item in add_content)
    sections.extend(
        [
            "",
            "## Deliverables",
        ]
    )
    sections.extend(f"- {item}" for item in deliverables)
    sections.extend(
        [
            "",
            "## Working memory",
        ]
    )
    sections.extend(f"- {item}" for item in learned_rules[:8])
    sections.extend(f"- {item}" for item in useful_pointers[:4])
    sections.extend(f"- {item}" for item in known_pitfalls[:4])
    sections.extend(
        [
            "",
            "## Skill routing",
            "- Prefer repo-local project skills under `.claude/skills/`.",
            "- The mirrored skills are generated from `.agents/skills/**/SKILL.md` and call the existing `90_System/Skills/**` automation code.",
            "- Keep external-service access inside the dedicated wrappers. Do not improvise direct Gmail, Slack, Fireflies, Todoist, Google Calendar, or Clockify access.",
            "- If a task involves local document editing outside the vault, create or update only an exported copy under `70_Exports/YYYY/MM/DD/` and report both source and exported paths.",
        ]
    )
    return "\n".join(sections) + "\n"


def build_settings() -> dict:
    deny_rules = [f"Read({glob})" for glob in SHARED_DENY_READ_GLOBS]
    deny_rules.extend(f"Edit({glob})" for glob in SHARED_DENY_EDIT_GLOBS)
    deny_rules.extend(
        [
            "Write(.git/**)",
            "Write(.venv/**)",
            "Write(.obsidian/**)",
            "Write(_attachments/**)",
            "Write(OneNoteNotes/**)",
            "Write(90_System/secrets/**)",
            "MultiEdit(.git/**)",
            "MultiEdit(.venv/**)",
            "MultiEdit(.obsidian/**)",
            "MultiEdit(_attachments/**)",
            "MultiEdit(OneNoteNotes/**)",
            "MultiEdit(90_System/secrets/**)",
        ]
    )

    allow_rules = [f"Bash({prefix}*)" for prefix in BASH_ALLOWLIST]

    return {
        "permissions": {
            "allow": allow_rules,
            "deny": deny_rules,
        },
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit|MultiEdit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "python .claude/hooks/pre_tool_use.py",
                        }
                    ],
                }
            ]
        },
    }


def copy_tree_contents(source: Path, destination: Path) -> None:
    for entry in source.iterdir():
        if entry.name == "SKILL.md":
            continue
        if entry.is_dir() and entry.name == "agents":
            continue
        target = destination / entry.name
        if entry.is_dir():
            shutil.copytree(entry, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(entry, target)


def build_skill_markdown(
    source_name: str,
    source_path: Path,
    body: str,
    frontmatter: dict[str, str],
    openai_meta: dict[str, str],
) -> str:
    description = frontmatter.get("description", "").strip()
    display_name = openai_meta.get("display_name", "").strip()
    default_prompt = openai_meta.get("default_prompt", "").strip()
    slug = slugify(source_name)
    skill_class = infer_skill_class(source_name)

    title, body_without_title = split_title(
        body, display_name or frontmatter.get("name", source_name)
    )

    parts = [
        "---",
        f'name: "{slug}"',
        f'description: "{description or display_name or source_name}"',
        "---",
        "",
        f"# {title}",
        "",
        f"This is a Claude Code mirror of `{source_name}` from `.agents/skills/`.",
        f"Original source: `{source_path.relative_to(REPO_ROOT).as_posix()}`",
        f"Skill class: `{skill_class}`",
    ]
    if default_prompt:
        parts.extend(
            [
                "",
                "## Default invocation",
                f"- {default_prompt}",
            ]
        )
    parts.extend(
        [
            "",
            body_without_title,
        ]
    )
    return "\n".join(parts).strip() + "\n"


def generate_skills() -> list[dict[str, str]]:
    remove_tree(CLAUDE_SKILLS_DIR)
    CLAUDE_SKILLS_DIR.mkdir(parents=True, exist_ok=True)

    manifest: list[dict[str, str]] = []
    used_slugs: set[str] = set()

    for source_dir in sorted(
        path for path in SOURCE_SKILLS_DIR.iterdir() if path.is_dir()
    ):
        skill_md = source_dir / "SKILL.md"
        if not skill_md.exists():
            continue

        source_name = source_dir.name
        slug = slugify(source_name)
        if slug in used_slugs:
            raise RuntimeError(f"Duplicate Claude skill slug: {slug}")
        used_slugs.add(slug)

        frontmatter, body = parse_frontmatter(read_text(skill_md))
        openai_meta = parse_simple_yaml(source_dir / "agents" / "openai.yaml")
        destination = CLAUDE_SKILLS_DIR / slug
        destination.mkdir(parents=True, exist_ok=True)

        write_text(
            destination / "SKILL.md",
            build_skill_markdown(source_name, skill_md, body, frontmatter, openai_meta),
        )
        copy_tree_contents(source_dir, destination)

        manifest.append(
            {
                "source_name": source_name,
                "claude_name": slug,
                "source_path": str(skill_md.relative_to(REPO_ROOT).as_posix()),
                "claude_path": str(
                    (destination / "SKILL.md").relative_to(REPO_ROOT).as_posix()
                ),
            }
        )

    return manifest


def generate_project_files(skill_manifest: Iterable[dict[str, str]]) -> None:
    write_text(REPO_ROOT / "CLAUDE.md", build_claude_md())
    write_text(CLAUDE_DIR / "README.md", CLAUDE_README)
    write_text(
        CLAUDE_DIR / "settings.local.example.json", CLAUDE_SETTINGS_LOCAL_EXAMPLE
    )
    write_text(CLAUDE_HOOKS_DIR / "pre_tool_use.py", PRE_TOOL_USE_SCRIPT)
    write_text(
        CLAUDE_DIR / "settings.json",
        json.dumps(build_settings(), indent=2, ensure_ascii=True),
    )
    write_text(
        CLAUDE_DIR / "generated-map.json",
        json.dumps({"skills": list(skill_manifest)}, indent=2, ensure_ascii=True),
    )


def main() -> int:
    CLAUDE_DIR.mkdir(parents=True, exist_ok=True)
    CLAUDE_HOOKS_DIR.mkdir(parents=True, exist_ok=True)
    skill_manifest = generate_skills()
    generate_project_files(skill_manifest)
    print(f"Generated Claude Code mirror with {len(skill_manifest)} skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
