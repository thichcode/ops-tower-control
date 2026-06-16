import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.config import AI_REVIEW_ENABLED, AI_REVIEW_MODEL, OPENAI_API_KEY
from app.models import AIReview, Service, User, WorkItem, WorkItemEvidence


VALID_STATUSES = {"Open", "Blocked", "Done"}


def queue_review(db: Session, item: WorkItem, reason: str | None = None) -> AIReview:
    review = db.query(AIReview).filter(
        AIReview.work_item_id == item.id,
        AIReview.state == "pending",
    ).first()
    evidence = build_evidence(db, item)
    suggestion = rule_based_suggestion(item)
    if reason:
        evidence["queue_reason"] = reason
    if review:
        review.evidence = evidence
        review.suggestion = suggestion
        return review
    review = AIReview(
        work_item_id=item.id,
        provider="rules",
        evidence=evidence,
        suggestion=suggestion,
    )
    db.add(review)
    return review


def create_or_refresh_review(db: Session, item: WorkItem, use_ai: bool = True) -> AIReview:
    evidence = build_evidence(db, item)
    suggestion = rule_based_suggestion(item)
    provider = "rules"
    model = None
    error = None

    if use_ai and AI_REVIEW_ENABLED and OPENAI_API_KEY:
        try:
            suggestion = request_openai_review(evidence)
            provider = "openai"
            model = AI_REVIEW_MODEL
        except Exception as exc:
            error = str(exc)[:1000]

    review = db.query(AIReview).filter(
        AIReview.work_item_id == item.id,
        AIReview.state == "pending",
    ).order_by(AIReview.created_at.desc()).first()
    if review:
        review.provider = provider
        review.model = model
        review.evidence = evidence
        review.suggestion = suggestion
        review.error = error
    else:
        review = AIReview(
            work_item_id=item.id,
            provider=provider,
            model=model,
            evidence=evidence,
            suggestion=suggestion,
            error=error,
        )
        db.add(review)
    db.commit()
    db.refresh(review)
    return review


def _redact_name(value: str | None) -> str | None:
    return "[REDACTED]" if value else value


def _redact_text(value: str | None) -> str | None:
    if not value:
        return value
    from app.services.member_intake import redact_text
    return redact_text(value)


def build_evidence(db: Session, item: WorkItem) -> dict[str, Any]:
    conversation = db.query(WorkItemEvidence).filter(
        WorkItemEvidence.work_item_id == item.id,
    ).order_by(WorkItemEvidence.created_at.asc()).all()
    thread_id = next((e.thread_id for e in conversation if e.thread_id), None)
    return {
        "work_item": {
            "id": item.id,
            "title": _redact_text(item.title) or "",
            "description": _redact_text(item.description) or "",
            "notes": _redact_text(item.notes) or "",
            "current_status": item.status,
            "current_service": item.service.name if item.service else None,
            "current_assignee": _redact_name(item.assignee.display_name if item.assignee else None),
            "source": item.source,
            "requester": _redact_name(item.requester_name),
        },
        "conversation": {
            "thread_id": thread_id,
            "message_count": len(conversation),
        },
        "allowed_statuses": sorted(VALID_STATUSES),
        "allowed_services": [service.name for service in db.query(Service).filter(Service.status == "active").all()],
        "allowed_assignees": [],
        "conversation_evidence": [
            {
                "sender": _redact_name(evidence.sender_name),
                "body": _redact_text(evidence.body_excerpt),
                "event_type": evidence.event_type,
                "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
            }
            for evidence in conversation
        ],
    }


def rule_based_suggestion(item: WorkItem) -> dict[str, Any]:
    reasons = []
    confidence = 0.7
    if item.notes and "Needs review:" in item.notes:
        reasons.append("The intake rules marked this item for human review.")
        confidence = 0.55
    else:
        reasons.append("No strong contradictory signal was found; preserve the current classification.")
    return {
        "status": item.status if item.status in VALID_STATUSES else "Open",
        "service": item.service.name if item.service else None,
        "assignee": item.assignee.display_name if item.assignee else None,
        "confidence": confidence,
        "rationale": " ".join(reasons),
        "signals": ["rule-based fallback"],
    }


def request_openai_review(evidence: dict[str, Any]) -> dict[str, Any]:
    schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": sorted(VALID_STATUSES)},
            "service": {"type": ["string", "null"]},
            "assignee": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "rationale": {"type": "string"},
            "signals": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
        },
        "required": ["status", "service", "assignee", "confidence", "rationale", "signals"],
        "additionalProperties": False,
    }
    payload = {
        "model": AI_REVIEW_MODEL,
        "store": False,
        "instructions": (
            "Review an operational work item classification. Use only the supplied evidence and allowed values. "
            "Do not infer completion from silence or age. Prefer preserving the current value when evidence is weak. "
            "Return a concise, auditable rationale. This is a recommendation for human approval, never an automatic decision."
        ),
        "input": json.dumps(evidence, ensure_ascii=False),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "work_item_review",
                "strict": True,
                "schema": schema,
            }
        },
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI review failed ({exc.code}): {detail[:500]}") from exc
    result = json.loads(_response_output_text(body))
    return validate_suggestion(result, evidence)


def validate_suggestion(suggestion: dict[str, Any], evidence: dict[str, Any]) -> dict[str, Any]:
    if suggestion.get("status") not in VALID_STATUSES:
        suggestion["status"] = "Open"
    if suggestion.get("service") not in evidence["allowed_services"]:
        suggestion["service"] = None
    if suggestion.get("assignee") not in evidence["allowed_assignees"]:
        suggestion["assignee"] = None
    suggestion["confidence"] = max(0.0, min(1.0, float(suggestion.get("confidence", 0))))
    suggestion["rationale"] = str(suggestion.get("rationale") or "No rationale provided.")[:1000]
    suggestion["signals"] = [str(signal)[:200] for signal in suggestion.get("signals", [])[:5]]
    return suggestion


def apply_review(
    db: Session,
    review: AIReview,
    status: str,
    service_id: int | None,
    assignee_id: int | None,
    reviewer_id: int | None = None,
) -> None:
    item = review.work_item
    item.status = status if status in VALID_STATUSES else item.status
    item.service_id = service_id
    item.assignee_id = assignee_id
    if item.status == "Done" and not item.completed_at:
        item.completed_at = datetime.now(timezone.utc)
    elif item.status != "Done":
        item.completed_at = None
    review.state = "approved"
    review.reviewer_id = reviewer_id
    review.reviewed_at = datetime.now(timezone.utc)
    db.commit()


def reject_review(
    db: Session,
    review: AIReview,
    reviewer_id: int | None = None,
) -> None:
    review.state = "rejected"
    review.reviewer_id = reviewer_id
    review.reviewed_at = datetime.now(timezone.utc)
    db.commit()


def _response_output_text(body: dict[str, Any]) -> str:
    if body.get("output_text"):
        return body["output_text"]
    for output in body.get("output", []):
        for content in output.get("content", []):
            if content.get("type") == "output_text":
                return content.get("text", "")
    raise RuntimeError("OpenAI response did not contain output text")
