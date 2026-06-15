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
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    if not token:
        return TemplateResponse("requester_status.html", {
            "request": request,
            "items": [],
            "search_name": "",
            "show_form": True,
        })

    items = db.query(WorkItem).filter(WorkItem.requester_token == token.strip()).order_by(WorkItem.created_at.desc()).all()
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    for item in items:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        item.age_days = (now - created).days

    return TemplateResponse("requester_status.html", {
        "request": request,
        "items": items,
        "search_name": "",
        "show_form": True,
    })
