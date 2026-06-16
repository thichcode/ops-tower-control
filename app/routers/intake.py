import secrets

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import role_required
from app.database import get_db
from app.models import WorkItem, WorkItemEvidence, User, Service
from app.services.ai_review import queue_review
from app.services.member_intake import redact_text
from app.services.parser import parse_teams_command

router = APIRouter(prefix="/api/intake", tags=["intake"])


class TeamsIntakePayload(BaseModel):
    command: str
    original_message_text: str
    reply_text: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    assignee_name: Optional[str] = None
    assignee_email: Optional[str] = None
    team_name: Optional[str] = None
    channel_name: Optional[str] = None
    message_id: Optional[str] = None
    conversation_id: Optional[str] = None
    message_url: Optional[str] = None
    created_at: Optional[str] = None


@router.post("/teams")
def intake_teams(payload: TeamsIntakePayload, db: Session = Depends(get_db)):
    source_message_id = f"Teams:{payload.message_id.strip()}" if payload.message_id else None
    if source_message_id:
        existing_evidence = db.query(WorkItemEvidence).filter(
            WorkItemEvidence.source_message_id == source_message_id
        ).first()
        if existing_evidence:
            item = db.get(WorkItem, existing_evidence.work_item_id)
            return _teams_response(item, evidence_attached=False, review_queued=False, duplicate=True)

    thread_item = None
    if payload.conversation_id:
        thread_item = db.query(WorkItem).join(
            WorkItemEvidence, WorkItemEvidence.work_item_id == WorkItem.id
        ).filter(
            WorkItemEvidence.source == "Teams",
            WorkItemEvidence.thread_id == payload.conversation_id.strip(),
        ).first()

    if thread_item:
        try:
            with db.begin_nested():
                db.add(_teams_evidence(payload, thread_item.id, source_message_id))
                db.flush()
                queue_review(db, thread_item, "New Teams conversation evidence")
        except IntegrityError:
            return _teams_response(thread_item, evidence_attached=False, review_queued=False, duplicate=True)
        db.commit()
        db.refresh(thread_item)
        return _teams_response(thread_item, evidence_attached=True, review_queued=True)

    try:
        with db.begin_nested():
            services = db.query(Service).filter(Service.status == "active").all()
            db_service_list = [{"id": s.id, "name": s.name} for s in services]

            parsed = parse_teams_command(payload.command, db_services=db_service_list)

            assignee = None
            if payload.assignee_email:
                assignee = db.query(User).filter(
                    User.email == payload.assignee_email, User.is_active == True
                ).first()

            title = payload.original_message_text.strip() or f"Task from {payload.sender_name or 'Teams'}"
            if parsed.get("title_suffix"):
                title = parsed["title_suffix"] + ": " + title

            item = WorkItem(
                title=title[:500],
                source="Teams",
                source_url=payload.message_url,
                requester_name=payload.sender_name,
                requester_email=payload.sender_email,
                assignee_id=assignee.id if assignee else None,
                work_type=parsed.get("work_type") or "Other",
                estimate_hours=parsed.get("estimate_hours"),
                service_id=parsed.get("service_hint", {}).get("id") if parsed.get("service_hint") else None,
                requester_token=secrets.token_urlsafe(16),
            )
            db.add(item)
            db.flush()
            db.add(_teams_evidence(payload, item.id, source_message_id))
    except IntegrityError:
        return {"id": None, "duplicate": True, "evidence_attached": False, "review_queued": False}

    db.commit()
    db.refresh(item)

    return _teams_response(item, assignee.display_name if assignee else None)


def _teams_evidence(payload: TeamsIntakePayload, item_id: int, source_message_id: str | None) -> WorkItemEvidence:
    body = payload.reply_text or payload.command or payload.original_message_text
    return WorkItemEvidence(
        work_item_id=item_id,
        source="Teams",
        source_message_id=source_message_id,
        thread_id=payload.conversation_id.strip() if payload.conversation_id else None,
        sender_name=payload.assignee_name or payload.sender_name,
        body_excerpt=redact_text(body),
        event_type="reply" if payload.reply_text else "message",
    )


def _teams_response(
    item: WorkItem,
    assignee: str | None = None,
    evidence_attached: bool = False,
    review_queued: bool = False,
    duplicate: bool = False,
) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "status": item.status,
        "source_url": item.source_url,
        "assignee": assignee or (item.assignee.display_name if item.assignee else None),
        "requester_token": item.requester_token,
        "evidence_attached": evidence_attached,
        "review_queued": review_queued,
        "duplicate": duplicate,
    }


@router.post("/package")
def intake_package(package: dict, db: Session = Depends(get_db)):
    from app.services.member_intake import import_member_package

    return import_member_package(db, package)


@router.post("/sdp")
def intake_sdp(mock: bool = False, dry_run: bool = False, db: Session = Depends(get_db), _=Depends(role_required("leader", "admin"))):
    from app.services.sdp_sync import sync_sdp_tickets
    stats = sync_sdp_tickets(db, mock=mock, dry_run=dry_run)
    return {"status": "ok", "stats": stats}


@router.post("/zabbix")
def intake_zabbix(mock: bool = False, dry_run: bool = False, db: Session = Depends(get_db), _=Depends(role_required("leader", "admin"))):
    from app.services.zabbix_sync import sync_zabbix_problems
    stats = sync_zabbix_problems(db, mock=mock, dry_run=dry_run)
    return {"status": "ok", "stats": stats}


@router.post("/digest")
def trigger_digest(dry_run: bool = False, db: Session = Depends(get_db), _=Depends(role_required("leader", "admin"))):
    from app.services.daily_digest import send_daily_digest
    result = send_daily_digest(db, dry_run=dry_run)
    return result


@router.post("/alerts")
def trigger_alerts(dry_run: bool = False, db: Session = Depends(get_db), _=Depends(role_required("leader", "admin"))):
    from app.services.leader_alerts import send_leader_alerts
    result = send_leader_alerts(db, dry_run=dry_run)
    return result


@router.post("/retention")
def trigger_retention_check(dry_run: bool = False, db: Session = Depends(get_db), _=Depends(role_required("leader", "admin"))):
    from app.services.retention_alerts import check_retention_alerts
    result = check_retention_alerts(db, dry_run=dry_run)
    return result
