# Member-Controlled Intake Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working slice of member-controlled intake: a local/private helper package format, server-side package import API, shared normalization/dedup logic, and basic tests.

**Architecture:** Add a focused `app/services/member_intake.py` service that validates package JSON, normalizes items, redacts text, resolves users/services, deduplicates by source id and title+assignee, and imports WorkItems. Reuse it from a new `/api/intake/package` endpoint and the existing `/import/upload` route so manual upload and helper POST behave consistently. Add `tools/member_helper.py` as a local script that builds packages from a local JSON file, previews output, writes packages, or POSTs to OpsDash.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, `unittest`, standard-library `argparse`, `json`, and `urllib.request`.

---

## File Structure

- Create: `app/services/member_intake.py` — package schema validation, redaction, normalization, dedup, and import result aggregation.
- Modify: `app/routers/intake.py` — add `POST /api/intake/package` for helper uploads.
- Modify: `app/routers/importer.py` — route package-shaped uploads through the shared service before falling back to old formats.
- Create: `tools/member_helper.py` — local/private helper CLI for preview/export/send.
- Create: `tests/test_member_intake.py` — unit tests for redaction, package import, duplicate handling, and review flags.
- Create: `tests/test_member_helper.py` — unit tests for helper package building.

## Task 1: Shared Member Intake Service

**Files:**
- Create: `app/services/member_intake.py`
- Test: `tests/test_member_intake.py`

- [ ] **Step 1: Write failing tests for redaction and package import**

Create `tests/test_member_intake.py` with in-memory SQLite setup and tests that import one Teams package, redact secrets, skip duplicates, and mark missing service for review.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_member_intake -v`

Expected: FAIL because `app.services.member_intake` does not exist.

- [ ] **Step 3: Implement `app/services/member_intake.py`**

Implement:

```python
SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+"),
]

def redact_text(text: str | None) -> str:
    ...

def import_member_package(db: Session, package: dict) -> dict:
    ...
```

The result shape must be `{"success": bool, "imported": int, "skipped": int, "review": int, "total": int, "errors": list[str]}`.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m unittest tests.test_member_intake -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run: `git add app/services/member_intake.py tests/test_member_intake.py && git commit -m "feat: add member intake import service"`

## Task 2: Import API And Upload Integration

**Files:**
- Modify: `app/routers/intake.py`
- Modify: `app/routers/importer.py`

- [ ] **Step 1: Write failing endpoint smoke test**

Add a test in `tests/test_member_intake.py` that calls the service directly for package-shaped JSON and verifies the same result shape the endpoint will return.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_member_intake -v`

Expected: FAIL until package-shaped upload is routed to shared logic.

- [ ] **Step 3: Add endpoint and upload branching**

In `app/routers/intake.py`, add:

```python
@router.post("/package")
def intake_package(package: dict, db: Session = Depends(get_db)):
    from app.services.member_intake import import_member_package
    return import_member_package(db, package)
```

In `app/routers/importer.py`, detect `schema_version` and `items` after JSON decode, call `import_member_package`, and render `import.html` with its result.

- [ ] **Step 4: Run tests and smoke import**

Run: `python -m unittest tests.test_member_intake -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run: `git add app/routers/intake.py app/routers/importer.py tests/test_member_intake.py && git commit -m "feat: add member package intake API"`

## Task 3: Local Helper CLI

**Files:**
- Create: `tools/member_helper.py`
- Test: `tests/test_member_helper.py`

- [ ] **Step 1: Write failing helper tests**

Create tests for building a package from local JSON input containing `items`, applying member metadata, redacting body excerpts, and writing package JSON.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m unittest tests.test_member_helper -v`

Expected: FAIL because `tools.member_helper` does not exist.

- [ ] **Step 3: Implement helper**

Implement CLI flags:

```text
--input path.json
--member-name "Engineer A"
--member-email engineer.a@example.com
--output package.json
--preview
--send-url http://localhost:8000/api/intake/package
```

The helper should read local JSON, normalize `items` or Power Automate `value` arrays into the package schema, redact body excerpts, print preview counts, write output if requested, and POST package JSON if `--send-url` is provided.

- [ ] **Step 4: Run helper tests**

Run: `python -m unittest tests.test_member_helper -v`

Expected: all tests PASS.

- [ ] **Step 5: Commit**

Run: `git add tools/member_helper.py tests/test_member_helper.py && git commit -m "feat: add local member intake helper"`

## Task 4: Final Verification

**Files:**
- Verify all touched files.

- [ ] **Step 1: Run full unittest suite**

Run: `python -m unittest discover -s tests -p "test_*.py" -v`

Expected: all tests PASS.

- [ ] **Step 2: Run import smoke check**

Run: `python -m py_compile app/services/member_intake.py app/routers/intake.py app/routers/importer.py tools/member_helper.py`

Expected: command exits 0.

- [ ] **Step 3: Check git status**

Run: `git status --short`

Expected: no uncommitted files.
