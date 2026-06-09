# Intake Accuracy Rules Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add deterministic confidence scoring, service aliases, and identity aliases to member-controlled intake without AI, database schema changes, or UI changes.

**Architecture:** Create `app/services/intake_rules.py` for code/config aliases and confidence constants. Update `app/services/member_intake.py` to use those rules, store readable confidence/review notes, and return aggregate confidence counts. Update `tools/member_helper.py` to use the same service alias detection before sending packages.

**Tech Stack:** Python 3.11, SQLAlchemy, standard-library `unittest`, existing FastAPI app modules.

---

## File Structure

- Create: `app/services/intake_rules.py` — deterministic alias maps, confidence constants, service alias resolution, identity alias resolution.
- Modify: `app/services/member_intake.py` — call intake rules, compute confidence, append confidence notes, return aggregate confidence counts.
- Modify: `tools/member_helper.py` — use intake rules for service alias detection.
- Modify: `tests/test_member_intake.py` — add tests for exact/alias/fallback confidence and notes.
- Modify: `tests/test_member_helper.py` — add helper alias detection test.

## Task 1: Intake Rules Module

**Files:**
- Create: `app/services/intake_rules.py`
- Modify: `tests/test_member_intake.py`

- [ ] **Step 1: Write failing tests for alias rules**

Add tests that expect:

```python
from app.services.intake_rules import resolve_service_alias, resolve_identity_alias

service_name, confidence, ambiguous = resolve_service_alias("please check k8s ingress")
self.assertEqual(service_name, "Kubernetes")
self.assertEqual(confidence, 0.85)
self.assertFalse(ambiguous)

identity = resolve_identity_alias(None, "A Nguyen", None, None, aliases={"engineer.a@example.com": ["A Nguyen"]})
self.assertEqual(identity["email"], "engineer.a@example.com")
self.assertEqual(identity["confidence"], 0.85)
```

- [ ] **Step 2: Run RED tests**

Run: `python -m unittest tests.test_member_intake -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.intake_rules'`.

- [ ] **Step 3: Implement `app/services/intake_rules.py`**

Implement constants and functions:

```python
CONFIDENCE_EXACT = 1.0
CONFIDENCE_ALIAS = 0.85
CONFIDENCE_FALLBACK = 0.7
CONFIDENCE_MISSING = 0.0
REVIEW_THRESHOLD = 0.8

SERVICE_ALIASES = {
    "Cloudflare": ["cloudflare", "cf", "dns", "waf"],
    "Kubernetes": ["kubernetes", "k8s", "pod", "ingress"],
    "Backup": ["backup", "veeam", "restore"],
    "ServiceDesk": ["servicedesk", "service desk", "sdp", "ticket"],
    "Zabbix": ["zabbix", "monitoring", "alert"],
    "GitLab": ["gitlab", "git", "repo", "pipeline", "ci"],
}

IDENTITY_ALIASES = {}

def resolve_service_alias(value, aliases=None):
    ...

def resolve_identity_alias(email, name, fallback_email, fallback_name, aliases=None):
    ...
```

- [ ] **Step 4: Run GREEN tests**

Run: `python -m unittest tests.test_member_intake -v`
Expected: all tests PASS.

## Task 2: Member Intake Confidence Notes

**Files:**
- Modify: `app/services/member_intake.py`
- Modify: `tests/test_member_intake.py`

- [ ] **Step 1: Write failing tests for confidence notes**

Add tests that expect:

```python
result = import_member_package(self.db, self.package(service_hint="dns"))
item = self.db.query(WorkItem).one()
self.assertEqual(item.service.name, "Cloudflare")
self.assertIn("Confidence: assignee=1.00, service=0.85", item.notes)
self.assertEqual(result["low_confidence"], 0)
```

Add a helper fallback test:

```python
pkg = self.package(assignee_email="", assignee_name="")
result = import_member_package(self.db, pkg)
item = self.db.query(WorkItem).one()
self.assertIn("assignee=0.70", item.notes)
self.assertIn("Needs review: low assignee confidence", item.notes)
self.assertEqual(result["low_confidence"], 1)
```

- [ ] **Step 2: Run RED tests**

Run: `python -m unittest tests.test_member_intake -v`
Expected: FAIL because `member_intake.py` does not yet compute confidence notes.

- [ ] **Step 3: Implement member intake confidence**

Update service/user/status resolution to return `(value, confidence, review_reason)` and build notes:

```python
confidence = {"assignee": assignee_conf, "service": service_conf, "status": status_conf}
overall = min(confidence.values())
notes.append(f"Confidence: assignee={assignee_conf:.2f}, service={service_conf:.2f}, status={status_conf:.2f}, overall={overall:.2f}")
```

Add result key `low_confidence` counting imported items with any field below `REVIEW_THRESHOLD`.

- [ ] **Step 4: Run GREEN tests**

Run: `python -m unittest tests.test_member_intake -v`
Expected: all tests PASS.

## Task 3: Helper Service Alias Detection

**Files:**
- Modify: `tools/member_helper.py`
- Modify: `tests/test_member_helper.py`

- [ ] **Step 1: Write failing helper alias test**

Add test:

```python
data = {"items": [{"source_id": "1", "title": "Check dns issue", "body_excerpt": "dns broken"}]}
package = build_package(data, "Engineer A", "engineer.a@example.com", previewed=True)
self.assertEqual(package["items"][0]["service_hint"], "Cloudflare")
```

- [ ] **Step 2: Run RED helper tests**

Run: `python -m unittest tests.test_member_helper -v`
Expected: FAIL because helper still uses local `KNOWN_SERVICES` exact matching.

- [ ] **Step 3: Update helper**

Import `resolve_service_alias` from `app.services.intake_rules`, remove local `KNOWN_SERVICES`, and use canonical alias result in `_detect_service`.

- [ ] **Step 4: Run GREEN helper tests**

Run: `python -m unittest tests.test_member_helper -v`
Expected: all tests PASS.

## Task 4: Final Verification

**Files:**
- Verify all touched files.

- [ ] **Step 1: Run explicit unittest discovery**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`
Expected: all tests PASS.

- [ ] **Step 2: Run compile check**

Run: `python -m py_compile app/services/intake_rules.py app/services/member_intake.py tools/member_helper.py`
Expected: command exits 0.

- [ ] **Step 3: Inspect status and diff**

Run: `git status --short` and `git diff --stat`
Expected: only intended files changed.
