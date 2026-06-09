import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import Service, User, WorkItem


SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|token|password|secret)\s*[:=]\s*\S+"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+"),
]

STATUS_TAG_RE = re.compile(r"\[(DONE|XONG|HOÀN THÀNH|BLOCKED|TẠM DỪNG|VƯỚNG|OPEN|ĐANG LÀM)\]", re.IGNORECASE)
STATUS_TAG_MAP = {
    "DONE": "Done",
    "XONG": "Done",
    "HOÀN THÀNH": "Done",
    "BLOCKED": "Blocked",
    "TẠM DỪNG": "Blocked",
    "VƯỚNG": "Blocked",
    "OPEN": "Open",
    "ĐANG LÀM": "Open",
}


def redact_text(text: str | None) -> str:
    if not text:
        return ""
    result = text
    for pattern in SECRET_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result


def import_member_package(db: Session, package: dict[str, Any]) -> dict[str, Any]:
    items = package.get("items")
    if package.get("schema_version") != "1.0" or not isinstance(items, list):
        return _result(False, 0, 0, 0, 0, ["Invalid member intake package"])

    imported = 0
    skipped = 0
    review = 0
    errors = []

    for index, evidence in enumerate(items, start=1):
        title = (evidence.get("title") or "").strip()
        if not title:
            skipped += 1
            errors.append(f"Item #{index}: missing title")
            continue

        source = (evidence.get("source") or "Unknown").strip() or "Unknown"
        source_id = _source_id(source, evidence.get("source_id"))
        if source_id and db.query(WorkItem).filter(WorkItem.source_id == source_id).first():
            skipped += 1
            continue

        assignee = _resolve_user(db, evidence)
        if _find_probable_duplicate(db, title, assignee.id if assignee else None, evidence.get("created_at")):
            skipped += 1
            continue

        service, service_review = _resolve_service(db, evidence.get("service_hint"))
        status = _detect_status(evidence)
        notes = []
        if service_review:
            notes.append("Needs review: unknown service")
        if not assignee:
            notes.append("Needs review: missing assignee")
        if notes:
            review += 1

        item = WorkItem(
            title=title[:500],
            description=redact_text(evidence.get("body_excerpt")),
            service_id=service.id if service else None,
            work_type=evidence.get("work_type") or "Other",
            source=source,
            source_url=evidence.get("source_url"),
            source_id=source_id,
            requester_name=evidence.get("sender_name"),
            requester_email=evidence.get("sender_email"),
            assignee_id=assignee.id if assignee else None,
            status=status,
            estimate_hours=_decimal_or_none(evidence.get("estimate_hours")),
            notes="; ".join(notes) if notes else None,
            created_at=_parse_datetime(evidence.get("created_at")),
            completed_at=datetime.now(timezone.utc) if status == "Done" else None,
        )
        db.add(item)
        imported += 1

    db.commit()
    return _result(imported > 0, imported, skipped, review, len(items), errors)


def _result(success: bool, imported: int, skipped: int, review: int, total: int, errors: list[str]) -> dict[str, Any]:
    return {
        "success": success,
        "imported": imported,
        "skipped": skipped,
        "review": review,
        "total": total,
        "errors": errors,
    }


def _source_id(source: str, raw_source_id: Any) -> str | None:
    if not raw_source_id:
        return None
    return f"{source}:{str(raw_source_id).strip()}"


def _resolve_user(db: Session, evidence: dict[str, Any]) -> User | None:
    email = (evidence.get("assignee_email") or "").strip()
    name = (evidence.get("assignee_name") or "").strip()
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return user
        user = User(display_name=name or email.split("@")[0], email=email, is_active=True)
        db.add(user)
        db.flush()
        return user
    if name:
        user = db.query(User).filter(User.display_name == name).first()
        if user:
            return user
        user = User(display_name=name, email=f"{name.lower().replace(' ', '.')}@imported.local", is_active=True)
        db.add(user)
        db.flush()
        return user
    return None


def _resolve_service(db: Session, service_hint: Any) -> tuple[Service | None, bool]:
    service_name = (service_hint or "").strip()
    if not service_name:
        return None, True
    service = db.query(Service).filter(Service.name == service_name).first()
    return service, service is None


def _detect_status(evidence: dict[str, Any]) -> str:
    text = f"{evidence.get('title') or ''} {evidence.get('body_excerpt') or ''}"
    tag_match = STATUS_TAG_RE.search(text)
    if tag_match:
        return STATUS_TAG_MAP.get(tag_match.group(1).upper(), "Open")
    status_hint = (evidence.get("status_hint") or "").strip().capitalize()
    if status_hint in {"Open", "Done", "Blocked"}:
        return status_hint
    return "Open"


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _decimal_or_none(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _find_probable_duplicate(db: Session, title: str, assignee_id: int | None, created_at: Any) -> WorkItem | None:
    if assignee_id is None:
        return None
    created = _parse_datetime(created_at)
    start = created - timedelta(days=7)
    end = created + timedelta(days=7)
    return db.query(WorkItem).filter(
        WorkItem.title == title,
        WorkItem.assignee_id == assignee_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).first()
