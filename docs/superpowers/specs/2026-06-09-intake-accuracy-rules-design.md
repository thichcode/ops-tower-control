# Intake Accuracy Rules Design

## Goal

Increase member-controlled intake accuracy without adding AI, database tables, or admin UI. The first slice adds code/config-based service aliases, identity aliases, and confidence scoring for imported package items.

## Direction

Keep the logic deterministic and auditable. Add a small rule module that maps known aliases to canonical services and users, then have `member_intake.py` use those rules when resolving service and assignee. Low-confidence fields should be imported with review notes instead of silently treated as correct.

## Non-Goals

- Do not add AI classification.
- Do not add database tables for mappings.
- Do not add a review UI in this slice.
- Do not change existing SDP/Teams legacy intake behavior unless it already routes through member package import.
- Do not make uncertain guesses look authoritative.

## Components

### `app/services/intake_rules.py`

Owns deterministic rules:

- `SERVICE_ALIASES`: canonical service name to aliases.
- `IDENTITY_ALIASES`: canonical email to aliases/names.
- `resolve_service_alias(text_or_hint)`: returns canonical service name and confidence.
- `resolve_identity_alias(email, name, fallback_email, fallback_name)`: returns canonical email/name and confidence.
- Confidence constants so thresholds are clear and testable.

### `app/services/member_intake.py`

Uses the rule module while importing package items:

- Exact service match in DB: confidence `1.0`.
- Alias service match: confidence `0.85`.
- Missing/unknown service: confidence `0.0`, add review note.
- Exact assignee email match: confidence `1.0`.
- Identity alias match: confidence `0.85`.
- Helper/member fallback: confidence `0.7`.
- Missing assignee: confidence `0.0`, add review note.

The import result should include aggregate confidence counts. Each WorkItem should store readable confidence details in `notes` because there is no schema change in this slice.

### `tools/member_helper.py`

Uses the same service alias logic when building package items so package hints improve before upload. The server still re-resolves the values because server-side import is the source of truth.

## Confidence Rules

Use simple decimal scores:

```text
1.00 = exact trusted signal
0.85 = configured alias match
0.70 = member/helper fallback
0.50 = weak hint, not used for auto-trust in this slice
0.00 = missing or unresolved
```

Field confidence below `0.80` creates a `Needs review` reason. Overall confidence is the minimum of assignee, service, and status confidence.

Status confidence in this slice:

- Explicit status tag: `1.0`.
- Valid `status_hint`: `0.85`.
- Default `Open`: `0.7` and review only if other fields are already uncertain.

## Notes Format

Store a readable text summary in `WorkItem.notes`:

```text
Confidence: assignee=0.85, service=0.85, status=1.00, overall=0.85
Needs review: unknown service; low assignee confidence
```

If the item already has review reasons, append the confidence summary without removing existing reasons.

## Example Rules

Initial service aliases:

```python
SERVICE_ALIASES = {
    "Cloudflare": ["cloudflare", "cf", "dns", "waf"],
    "Kubernetes": ["kubernetes", "k8s", "pod", "ingress"],
    "Backup": ["backup", "veeam", "restore"],
    "ServiceDesk": ["servicedesk", "service desk", "sdp", "ticket"],
    "Zabbix": ["zabbix", "monitoring", "alert"],
    "GitLab": ["gitlab", "git", "repo", "pipeline", "ci"],
}
```

Initial identity aliases should be intentionally small and editable in code. The default implementation can ship with an empty mapping and tests can define sample aliases through function arguments or patching.

## Error Handling

- Alias resolves to a service that does not exist in DB: leave service empty and add review note.
- Alias resolves to identity email not present in DB: create user using current import behavior.
- Multiple service aliases match one item: choose the longest alias match; if tied, choose no service and mark review.
- Invalid package data should continue returning the existing invalid package result.

## Testing

- Unit test exact service confidence.
- Unit test alias service confidence.
- Unit test unknown service review note.
- Unit test exact email identity confidence.
- Unit test identity alias confidence.
- Unit test helper fallback identity confidence.
- Unit test confidence summary appears in `WorkItem.notes`.
- Unit test helper uses alias service detection.

## Success Criteria

- More items auto-resolve service from common aliases like `dns`, `k8s`, `sdp`, and `veeam`.
- Member aliases can resolve to one canonical user without AI.
- Low-confidence imports are visibly marked for review.
- Existing 8 member intake/helper tests continue passing.
