---
type: slack-thread
source: slack
workspace: "{{workspace}}"
team_id: "{{team_id}}"
conversation_id: "{{conversation_id}}"
conversation_name: "{{conversation_name}}"
conversation_kind: "{{conversation_kind}}"
thread_ts: "{{thread_ts}}"
retention_class: "{{retention_class}}"
last_message_at: "{{last_message_at}}"
stored_at: "{{stored_at}}"
permalink: "{{permalink}}"
project: ""
participants:
{{participants_yaml}}
---

# Slack Thread

## Thread
- Workspace: {{workspace}}
- Conversation: {{conversation_name}} ({{conversation_kind}})
- Conversation ID: {{conversation_id}}
- Thread TS: {{thread_ts}}
- Last message: {{last_message_at}}
- Stored: {{stored_at}}
- Retention: {{retention_class}}
- Permalink: {{permalink}}
- Project:

## Participants
- People: {{linked_people}}
- Slack participants: {{participants_inline}}

## Notes
- Why this matters:
- Next action:

## Messages
{{messages_block}}
