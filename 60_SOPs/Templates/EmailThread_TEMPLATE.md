---
type: email-thread
account: "{{account}}"
thread_id: "{{thread_id}}"
subject: "{{subject}}"
project: ""
last_message_at: "{{last_message_at}}"
stored_at: "{{stored_at}}"
participants:
{{emails_yaml}}
---

# {{subject}}

## Thread
- Account: {{account}}
- Thread ID: {{thread_id}}
- Last message: {{last_message_at}}
- Stored: {{stored_at}}
- Project:

## Participants
- Emails: {{participants_inline}}

## Notes
- Why this matters:
- Next action:

## Messages
{{messages_block}}
