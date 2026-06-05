from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import WorkItem
from app.templates import TemplateResponse

router = APIRouter(prefix="/requester", tags=["requester"])


@router.get("/status")
def requester_status(
    request: Request,
    name: Optional[str] = Query(None),
    email: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(WorkItem)
    if name:
        query = query.filter(WorkItem.requester_name.ilike(f"%{name}%"))
    if email:
        query = query.filter(WorkItem.requester_email.ilike(f"%{email}%"))

    if not name and not email:
        # Show top requesters list
        from sqlalchemy import func
        requesters = db.query(
            WorkItem.requester_name,
            func.count(WorkItem.id).label("total"),
        ).filter(
            WorkItem.requester_name.isnot(None),
            WorkItem.requester_name != "",
        ).group_by(WorkItem.requester_name).order_by(
            func.count(WorkItem.id).desc()
        ).limit(20).all()

        return TemplateResponse("requester_status.html", {
            "request": request,
            "requesters": [{"name": r.requester_name, "total": int(r.total)} for r in requesters],
            "items": [],
            "search_name": "",
        })

    items = query.order_by(WorkItem.created_at.desc()).all()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for item in items:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        item.age_days = (now - created).days

    return TemplateResponse("requester_status.html", {
        "request": request,
        "requesters": [],
        "items": items,
        "search_name": name or email or "",
    })
