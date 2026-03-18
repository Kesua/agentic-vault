# Slack Setup

## 1. Create the Slack app

Create a new Slack app from the read-only manifest:

- Manifest file: `90_System/Integrations/slack/app_manifest.readonly.yaml`
- Slack manifests: https://api.slack.com/tools/manifests

Recommended flow:

1. Open Slack app management.
2. Choose `Create New App`.
3. Choose `From an app manifest`.
4. Pick the target workspace.
5. Paste the YAML from `app_manifest.readonly.yaml`.
6. Create the app.

This manifest already enables token rotation and the read scopes used by the vault integration.

## 2. Install the app into the workspace

After the app exists:

1. Open the app settings.
2. Go to the OAuth/install section.
3. Install the app to the workspace.
4. Approve the requested scopes.

References:

- OAuth install: https://api.slack.com/authentication/oauth-v2
- Token rotation: https://api.slack.com/authentication/rotation

Notes:

- In a company workspace, a workspace admin or owner may need to approve the app.
- For private channels, the app must also be added to those channels or it may not be able to read them.

## 3. Get the secret correctly

For this repo, the required secret is the Slack read app bot token.

After installation, copy:

- `Bot User OAuth Token`

Store it in a local untracked file, for example:

- `90_System/secrets/slack_token_private.txt`

The file should contain only the token:

```txt
xoxe.xoxb-1234567890-1234567890-abcdefghijklmnop
```

Do not store the token in:

- `workspaces.json`
- Markdown notes
- committed YAML
- screenshots or saved logs

## 4. Prepare `workspaces.json`

Copy:

- `90_System/Integrations/slack/workspaces.example.json`

to:

- `90_System/Integrations/slack/workspaces.json`

That real file is already gitignored.

Use this structure:

```json
{
  "workspaces": [
    {
      "alias": "private",
      "team_id": "T01234567",
      "token_file": "90_System/secrets/slack_token_private.txt",
      "jan_user_ids": [
        "U01234567"
      ],
      "download": {
        "enabled": false,
        "max_bytes": 26214400,
        "allowed_extensions": [
          ".csv",
          ".docx",
          ".jpg",
          ".md",
          ".pdf",
          ".png",
          ".pptx",
          ".txt",
          ".xlsx"
        ]
      },
      "allow_conversations": [
        {
          "id": "C01234567",
          "name": "leadership",
          "type": "public_channel",
          "retention_class": "work",
          "allow_file_download": false
        },
        {
          "id": "G01234567",
          "name": "exec-private",
          "type": "private_channel",
          "retention_class": "work-private",
          "allow_file_download": false
        },
        {
          "id": "D01234567",
          "name": "dm-ops",
          "type": "im",
          "retention_class": "work-private",
          "allow_file_download": false
        }
      ]
    }
  ]
}
```

## 5. Meaning of each field

- `alias`
  - Local name for the workspace, for example `private` or `personal`
- `team_id`
  - Slack workspace ID, starts with `T`
- `token_file`
  - Path to the local token text file
- `jan_user_ids`
  - Jan’s Slack user IDs in that workspace, starts with `U`
  - Used to detect `waiting on your reply`
- `download.enabled`
  - Keep `false` initially
- `download.max_bytes`
  - Maximum allowed file size for download
- `download.allowed_extensions`
  - Safe allowlist only
- `allow_conversations`
  - Explicit allowlist of channels or DMs the sync may read
- `allow_conversations[].id`
  - Slack conversation ID
  - `C...` for public channel
  - `G...` for private channel or group DM
  - `D...` for DM
- `allow_conversations[].name`
  - Friendly label for local output
- `allow_conversations[].type`
  - One of `public_channel`, `private_channel`, `im`, `mpim`
- `retention_class`
  - Local classification such as `work`, `work-private`, `sensitive`
- `allow_file_download`
  - Keep `false` unless explicitly needed

## 6. How to get conversation IDs

After the token and config file exist, run:

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py list-conversations --workspace private
```

This prints conversation IDs and names. Copy only the conversations you want into `allow_conversations`.

## 7. How to get Jan user IDs

Practical approach:

1. Put a minimal `workspaces.json` in place with the token file and workspace alias.
2. Run:

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py auth-check --workspace private
```

3. Use Slack UI or admin tooling to confirm Jan’s user ID if needed.

If needed later, a small helper command such as `whoami` can be added to the skill.

## 8. First safe validation

Run these commands in order:

```powershell
.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py auth-check --workspace private
.\.venv\Scripts\python.exe 90_System\Skills\slack_assistant\slack_assistant.py list-conversations --workspace private
.\.venv\Scripts\python.exe 90_System\Skills\process_slack\process_slack.py sync --workspace private --dry-run
```

This verifies:

- the token works
- scopes are sufficient
- the workspace alias resolves
- allowed conversations are readable
- export paths are correct before writing notes

## 9. Security defaults to keep

- Use one Slack app per workspace or security boundary
- Keep `download.enabled` off initially
- Start with channels only, then add DMs selectively
- Keep the allowlist small
- Do not use the future write manifest for this read integration
- In corporate workspaces, get approval before enabling `users:read.email` or broad DM scopes

## 10. Slack references

- App manifests: https://api.slack.com/tools/manifests
- OAuth install: https://api.slack.com/authentication/oauth-v2
- Token rotation: https://api.slack.com/authentication/rotation
- Quickstart: https://api.slack.com/authentication/quickstart
