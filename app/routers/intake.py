from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import WorkItem, User, Service
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
    message_url: Optional[str] = None
    created_at: Optional[str] = None


@router.post("/teams")
def intake_teams(payload: TeamsIntakePayload, db: Session = Depends(get_db)):
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
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    return {
        "id": item.id,
        "title": item.title,
        "status": item.status,
        "source_url": item.source_url,
        "assignee": assignee.display_name if assignee else None,
    }


@router.post("/sdp")
def intake_sdp(mock: bool = False, dry_run: bool = False, db: Session = Depends(get_db)):
    from app.services.sdp_sync import sync_sdp_tickets
    stats = sync_sdp_tickets(db, mock=mock, dry_run=dry_run)
    return {"status": "ok", "stats": stats}


@router.post("/zabbix")
def intake_zabbix(mock: bool = False, dry_run: bool = False, db: Session = Depends(get_db)):
    from app.services.zabbix_sync import sync_zabbix_problems
    stats = sync_zabbix_problems(db, mock=mock, dry_run=dry_run)
    return {"status": "ok", "stats": stats}


@router.post("/digest")
def trigger_digest(dry_run: bool = False, db: Session = Depends(get_db)):
    from app.services.daily_digest import send_daily_digest
    result = send_daily_digest(db, dry_run=dry_run)
    return result


@router.post("/alerts")
def trigger_alerts(dry_run: bool = False, db: Session = Depends(get_db)):
    from app.services.leader_alerts import send_leader_alerts
    result = send_leader_alerts(db, dry_run=dry_run)
    return result
