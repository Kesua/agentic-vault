# Codex setup (repo-local)

This vault includes repo-local Codex configuration, command approval rules, and wrapper skills so contributors can use the same automations out of the box.

## What's included
- `.codex/config.toml`: default sandbox, approvals, model, and allowed roots
- `.codex/rules/*.rules`: optional command approval rules
- `.codex/file_access_policy.toml`: human-readable allow and deny patterns
- `.agents/skills/**/SKILL.md`: repo-local wrapper skills

## Notes
- Adjust `.codex/config.toml` for your local machine and any approved external repos.
- If your Codex installation does not pick up repo-local rules automatically, copy the relevant `.rules` file into your user rules directory.
