import re
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.models import Service, User, WorkItem
from app.services.intake_rules import (
    CONFIDENCE_ALIAS,
    CONFIDENCE_EXACT,
    CONFIDENCE_FALLBACK,
    CONFIDENCE_MISSING,
    REVIEW_THRESHOLD,
    resolve_identity_alias,
    resolve_service_alias,
)


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
    low_confidence = 0
    errors = []
    collector = package.get("collector") if isinstance(package.get("collector"), dict) else {}

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

        assignee, assignee_conf = _resolve_user(db, evidence, collector)
        if _find_probable_duplicate(db, title, assignee.id if assignee else None, evidence.get("created_at")):
            skipped += 1
            continue

        service, service_conf, service_review = _resolve_service(db, evidence, title)
        status, status_conf = _detect_status(evidence)
        overall_conf = min(assignee_conf, service_conf, status_conf)
        review_reasons = []
        if assignee_conf < REVIEW_THRESHOLD:
            review_reasons.append("Needs review: low assignee confidence")
        if service_review:
            review_reasons.append("Needs review: unknown service")
        elif service_conf < REVIEW_THRESHOLD:
            review_reasons.append("Needs review: low service confidence")
        if status_conf < REVIEW_THRESHOLD and (assignee_conf < REVIEW_THRESHOLD or service_conf < REVIEW_THRESHOLD):
            review_reasons.append("Needs review: low status confidence")
        notes = review_reasons + [_confidence_note(assignee_conf, service_conf, status_conf, overall_conf)]
        if review_reasons:
            review += 1
        if overall_conf < REVIEW_THRESHOLD:
            low_confidence += 1

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
    return _result(imported > 0, imported, skipped, review, len(items), errors, low_confidence)


def _result(success: bool, imported: int, skipped: int, review: int, total: int, errors: list[str], low_confidence: int = 0) -> dict[str, Any]:
    return {
        "success": success,
        "imported": imported,
        "skipped": skipped,
        "review": review,
        "low_confidence": low_confidence,
        "total": total,
        "errors": errors,
    }


def _source_id(source: str, raw_source_id: Any) -> str | None:
    if not raw_source_id:
        return None
    return f"{source}:{str(raw_source_id).strip()}"


def _resolve_user(db: Session, evidence: dict[str, Any], collector: dict[str, Any]) -> tuple[User | None, float]:
    identity = resolve_identity_alias(
        evidence.get("assignee_email"),
        evidence.get("assignee_name"),
        collector.get("member_email"),
        collector.get("member_name"),
    )
    email = (identity.get("email") or "").strip()
    name = (identity.get("name") or "").strip()
    confidence = float(identity.get("confidence") or CONFIDENCE_MISSING)
    if email:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return user, confidence
        user = User(display_name=name or email.split("@")[0], email=email, is_active=True)
        db.add(user)
        db.flush()
        return user, confidence
    if name:
        user = db.query(User).filter(User.display_name == name).first()
        if user:
            return user, confidence
        user = User(display_name=name, email=f"{name.lower().replace(' ', '.')}@imported.local", is_active=True)
        db.add(user)
        db.flush()
        return user, confidence
    return None, confidence


def _resolve_service(db: Session, evidence: dict[str, Any], title: str) -> tuple[Service | None, float, bool]:
    service_hint = evidence.get("service_hint")
    service_name = (service_hint or "").strip()
    if service_name:
        service = db.query(Service).filter(Service.name == service_name).first()
        if service:
            return service, CONFIDENCE_EXACT, False
        alias_name, alias_conf, ambiguous = resolve_service_alias(service_name)
        if alias_name and not ambiguous:
            service = db.query(Service).filter(Service.name == alias_name).first()
            if service:
                return service, alias_conf, False
        return None, CONFIDENCE_MISSING, True

    alias_text = f"{title} {evidence.get('body_excerpt') or ''}"
    alias_name, alias_conf, ambiguous = resolve_service_alias(alias_text)
    if alias_name and not ambiguous:
        service = db.query(Service).filter(Service.name == alias_name).first()
        if service:
            return service, alias_conf, False
    return None, CONFIDENCE_MISSING, True


def _detect_status(evidence: dict[str, Any]) -> tuple[str, float]:
    text = f"{evidence.get('title') or ''} {evidence.get('body_excerpt') or ''}"
    tag_match = STATUS_TAG_RE.search(text)
    if tag_match:
        return STATUS_TAG_MAP.get(tag_match.group(1).upper(), "Open"), CONFIDENCE_EXACT
    status_hint = (evidence.get("status_hint") or "").strip().capitalize()
    if status_hint in {"Open", "Done", "Blocked"}:
        return status_hint, CONFIDENCE_ALIAS
    return "Open", CONFIDENCE_FALLBACK


def _confidence_note(assignee_conf: float, service_conf: float, status_conf: float, overall_conf: float) -> str:
    return f"Confidence: assignee={assignee_conf:.2f}, service={service_conf:.2f}, status={status_conf:.2f}, overall={overall_conf:.2f}"


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
