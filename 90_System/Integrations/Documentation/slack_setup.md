# Slack read setup

The vault reads Slack with a **User OAuth Token**. It can discover channels visible to that user. Direct messages and group direct messages are included only when a command uses `--include-dm` and `--include-mpim`; the regular Slack wrapper uses both flags. `exclude_conversation_ids` removes named conversations from discovery and export.

## Set up

1. Create a Slack app in the workspace from `90_System/Integrations/slack/app_manifest.readonly.yaml`. The manifest requests user read scopes and no Slack write scope. A workspace administrator may need to approve the app.
2. Install the app and copy its **User OAuth Token** into `90_System/secrets/slack_user_token_<alias>.txt` (for example, `slack_user_token_private.txt`). Keep this file local and ignored by Git. Do not paste the token into notes or `workspaces.json`.
3. Copy `90_System/Integrations/slack/workspaces.example.json` to `90_System/Integrations/slack/workspaces.json`. This local config is ignored by Git. Set `alias`, `team_id`, and `self_user_ids` for the token owner. `auth-check` reports the user ID.
4. Leave `exclude_conversation_ids` empty to read all visible conversations of the selected types, or add IDs that must be skipped. Keep `download.enabled` false unless file download is needed.
5. Run the checks below before the first export.

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py auth-check --workspace private
.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py list-conversations --workspace private --source user --types "public_channel,private_channel,im,mpim"
.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --workspace private --dry-run --include-dm --include-mpim
```

When the dry run shows the intended scope, run the same `sync` command without `--dry-run`. Omit the DM flags for channels only. The regular wrapper includes the DM flags.

## Existing bot setup

A prior `token_file` plus `allow_conversations` config does not work with user-token reads. Use the setup wizard again or replace that local config with the example above and provide a User OAuth Token. The old bot token file can remain ignored locally until you remove it yourself; it is not used for the new read sync.

## Data boundaries

- Tokens stay under `90_System/secrets/`; conversation config and sync checkpoints stay in ignored local files.
- The read manifest has no message-posting scopes. `draft-message` and `draft-reply` remain disabled in the runtime.
- The manifest disables token rotation because this runtime does not refresh expiring Slack tokens. If your workspace requires rotation, replace the local token when it expires.
