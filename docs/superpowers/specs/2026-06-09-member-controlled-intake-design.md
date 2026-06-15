# Member-Controlled Intake Design

## Goal

OpsDash should capture operational evidence from Teams, email, and SDP while keeping member effort very low and preserving privacy. Members should not use OpsDash as a daily task manager. They should continue working in Teams, email, and SDP, while OpsDash receives only filtered evidence that is safe to share.

## Direction

Use a local/private helper script on each member machine to collect and filter Teams/email evidence before sending it to OpsDash. SDP remains a server-side sync source because it is already a formal work system. OpsDash becomes the aggregation, deduplication, review, dashboard, and reporting layer.

This avoids server-side scanning of private Teams messages and reduces member interaction to setup, optional preview, and mostly scheduled collection.

## Non-Goals

- Do not make OpsDash the primary place where members update daily work.
- Do not require members to manually create every task in the web UI.
- Do not give the OpsDash server broad access to all Teams messages.
- Do not replace SDP as the official ticket source.
- Do not require AI classification before the helper/package flow works.

## Member Experience

1. Member installs/configures the helper once.
2. Helper runs manually or on a local schedule.
3. Helper collects only allowed Teams/email content according to local rules.
4. Helper filters, redacts, and builds an import package.
5. Member can run preview/dry-run to see exactly what would be sent.
6. Helper sends the package to OpsDash or writes a file for upload.
7. Lead/admin reviews exceptions when OpsDash cannot classify confidently.

Daily expected behavior: member does not open OpsDash unless there is an exception or a periodic review.

## Sources

### SDP

SDP is the strongest source for formal tickets. OpsDash should continue syncing SDP server-side using the existing SDP integration. SDP records should be preferred when deduplicating against Teams/email evidence.

### Teams

Teams collection is member-controlled. The server does not read all Teams messages. The helper runs on the member machine and collects only messages that match local allow rules, such as allowed channels, selected threads, keywords, date ranges, or explicit export files.

### Email

Email can use the same helper pattern as Teams when privacy matters. The helper should support mailbox rules such as folders, senders, subjects, keywords, and date ranges. Server-side mailbox sync is allowed only for shared or explicitly approved mailboxes.

## Import Package Schema

The helper sends a JSON package with package metadata and normalized evidence items.

```json
{
  "schema_version": "1.0",
  "collector": {
    "type": "local-helper",
    "version": "0.1.0",
    "member_name": "Engineer A",
    "member_email": "engineer.a@example.com",
    "collected_at": "2026-06-09T09:00:00Z"
  },
  "privacy": {
    "mode": "filtered",
    "ruleset_name": "default-work-evidence",
    "previewed_by_member": true,
    "redaction_enabled": true
  },
  "items": [
    {
      "source": "Teams",
      "source_id": "teams-message-id",
      "source_url": "https://teams.microsoft.com/...",
      "thread_id": "thread-or-conversation-id",
      "created_at": "2026-06-09T08:30:00Z",
      "sender_name": "Requester A",
      "sender_email": "requester.a@example.com",
      "assignee_name": "Engineer A",
      "assignee_email": "engineer.a@example.com",
      "title": "Restore Cloudflare DNS for production site",
      "body_excerpt": "Restore Cloudflare DNS for production site [DONE]",
      "service_hint": "Cloudflare",
      "status_hint": "Done",
      "estimate_hours": null,
      "privacy_labels": ["member-approved", "redacted"]
    }
  ]
}
```

The schema should stay small at first. Additional fields can be added later, but import should not depend on perfect classification from the helper.

## Server Flow

```text
Local helper package
        ↓
OpsDash import API / file upload
        ↓
Package validation
        ↓
Parser and normalization
        ↓
Dedup against SDP, existing WorkItem.source_id, and title+assignee
        ↓
Create or update WorkItem
        ↓
Needs Review for low-confidence items
        ↓
Dashboards, alerts, scorecards, retention signals
```

## Dedup Rules

1. Exact `source + source_id` match updates the existing item.
2. SDP ticket ID match wins over Teams/email evidence.
3. Same normalized title, assignee, and timestamp within 7 days should be treated as a probable duplicate.
4. Probable duplicates should not create new WorkItems automatically; they should attach evidence or go to review.

## Status Handling

Status can come from several signals:

- SDP status when linked to an SDP ticket.
- Explicit convention tags such as `[DONE]`, `[BLOCKED]`, `[OPEN]`, `[XONG]`, `[TẠM DỪNG]`.
- Email/Teams text patterns as a fallback.

Confidence order should be: SDP status, explicit tag, helper-provided status hint, keyword fallback. Low-confidence status should be left as `Open` and marked for review.

## Review Queue

Add a `Needs Review` queue for items that are useful but uncertain. Review reasons include missing assignee, unknown service, probable duplicate, low-confidence status, or invalid date. This queue is for lead/admin cleanup, not daily member operation.

## Privacy Requirements

- The helper must support `dry-run`/preview before sending.
- The helper should redact obvious secrets and sensitive tokens from body excerpts.
- The server stores only filtered package data, not full private Teams/email history.
- Every package should include privacy metadata showing whether it was previewed and whether redaction ran.
- Members can choose file export instead of direct upload when they want manual control.

## Components

### Local Helper

Responsibilities:

- Read local/exported Teams and email data.
- Apply allow rules.
- Detect basic service/status hints.
- Redact sensitive strings.
- Produce package JSON.
- Optionally POST the package to OpsDash.

### Import API

Responsibilities:

- Accept package JSON.
- Validate schema version and required fields.
- Reuse existing import parser logic where possible.
- Return imported/skipped/review counts.

### Parser/Normalizer

Responsibilities:

- Convert evidence items into WorkItem create/update candidates.
- Resolve assignee and service.
- Detect status from explicit tags and hints.
- Produce confidence flags.

### Needs Review UI

Responsibilities:

- Show only uncertain items.
- Let lead/admin fix assignee, service, status, duplicate handling.
- Keep member interaction optional.

## Error Handling

- Invalid package: reject with a clear validation error and no partial import.
- Duplicate package: skip already imported items and report skipped count.
- Partial item errors: import valid items and return per-item warnings.
- Missing user/service: create a safe imported record only when current behavior already supports it; otherwise send to review.
- Upload failure from helper: write package locally so the member can retry or upload manually.

## Testing

- Unit tests for package validation.
- Unit tests for Teams/email item normalization.
- Unit tests for status tag detection and redaction.
- Unit tests for duplicate handling by `source_id`, SDP ticket ID, and title+assignee.
- Integration test for package import returning imported/skipped/review counts.
- Manual test with a dry-run package generated by the helper.

## Rollout Plan

1. Define package schema and server-side import API.
2. Refactor existing JSON import parsing so upload and API import share normalization logic.
3. Add review flags/counts without building a large workflow system.
4. Build a minimal helper that reads a local JSON/CSV export and produces the package schema.
5. Add optional direct POST from helper to OpsDash.
6. Add email collection after the package flow is stable.

## Success Criteria

- Members do not need to open OpsDash daily.
- Teams data is collected only on the member machine or from member-approved exports.
- OpsDash can import filtered packages and deduplicate them with existing WorkItems.
- Lead/admin can see useful dashboards without asking members to manually enter every task.
- Uncertain items are isolated in review instead of polluting dashboards.
