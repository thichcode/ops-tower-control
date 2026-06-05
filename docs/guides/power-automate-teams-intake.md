# Power Automate — Teams Intake Setup

## Trigger

Flow type: **Automated cloud flow**

Trigger: **When a new channel message is replied to** (Teams connector)

## Steps

### Step 1: Trigger

- **Connector:** Microsoft Teams
- **Trigger:** When a new channel message is replied to
- **Team:** [Your Team]
- **Channel:** [Your Channel]

### Step 2: Condition — Check if reply contains `/task`

```
@contains(triggerOutputs()?['body/reply/content'], '/task')
```

If true → continue. If false → terminate.

### Step 3: Compose — Extract fields

Use the "Compose" action to build the JSON payload:

```json
{
  "command": "@{triggerOutputs()?['body/reply/content']}",
  "original_message_text": "@{triggerOutputs()?['body/rootMessage/content']}",
  "reply_text": "@{triggerOutputs()?['body/reply/content']}",
  "sender_name": "@{triggerOutputs()?['body/rootMessage/from/user/displayName']}",
  "sender_email": "@{triggerOutputs()?['body/rootMessage/from/user/userPrincipalName']}",
  "assignee_name": "@{triggerOutputs()?['body/reply/from/user/displayName']}",
  "assignee_email": "@{triggerOutputs()?['body/reply/from/user/userPrincipalName']}",
  "team_name": "@{triggerOutputs()?['body/teamName']}",
  "channel_name": "@{triggerOutputs()?['body/channelName']}",
  "message_url": "@{triggerOutputs()?['body/reply/webUrl']}",
  "created_at": "@{utcNow()}"
}
```

### Step 4: HTTP — Send to Ops Control Tower

- **Method:** POST
- **URI:** `https://[your-server]/api/intake/teams`
- **Headers:**
  - `Content-Type`: application/json
- **Body:** Output from Step 3

### Step 5: Response action (optional)

Post a reply in the thread:

```
Task captured: @{body('HTTP')?['title']} (ID: @{body('HTTP')?['id']})
```

---

## Alternative: Simple Flow (no Power Automate)

Team members can also manually create tasks via the web Quick Add button.
