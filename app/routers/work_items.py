import secrets

from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.database import get_db
from app.models import WorkItem, User, Service
from app.templates import TemplateResponse

router = APIRouter()


@router.get("/")
def my_work(
    request: Request,
    status: Optional[str] = None,
    assignee_id: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(WorkItem)
    if status:
        query = query.filter(WorkItem.status == status)
    if assignee_id:
        query = query.filter(WorkItem.assignee_id == assignee_id)
    if q:
        query = query.filter(WorkItem.title.ilike(f"%{q}%"))
    work_items = query.order_by(WorkItem.created_at.desc()).all()

    now = datetime.now(timezone.utc)
    for item in work_items:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        item.age_days = (now - created).days

    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()
    services = db.query(Service).filter(Service.status == "active").order_by(Service.name).all()

    return TemplateResponse("my_work.html", {
        "request": request,
        "work_items": work_items,
        "users": users,
        "services": services,
    })


@router.post("/work-items")
def create_work_item(
    title: str = Form(...),
    description: Optional[str] = Form(None),
    service_id: Optional[int] = Form(None),
    work_type: Optional[str] = Form("Other"),
    requester_name: Optional[str] = Form(None),
    assignee_id: Optional[int] = Form(None),
    estimate_hours: Optional[Decimal] = Form(None),
    db: Session = Depends(get_db),
):
    item = WorkItem(
        title=title,
        description=description,
        service_id=service_id,
        work_type=work_type,
        requester_name=requester_name,
        assignee_id=assignee_id,
        estimate_hours=estimate_hours,
        requester_token=secrets.token_urlsafe(16),
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/work-items/{item_id}/done")
def done_work_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.status = "Done"
        item.completed_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/work-items/{item_id}/blocked")
def block_work_item(item_id: int, reason: Optional[str] = Form(None), db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.status = "Blocked"
        item.blocked_reason = reason
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/work-items/{item_id}/edit")
def edit_work_item(request: Request, item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()
    services = db.query(Service).order_by(Service.name).all()
    return TemplateResponse("work_item_form.html", {
        "request": request,
        "item": item,
        "users": users,
        "services": services,
    })


@router.post("/work-items/{item_id}/edit")
def update_work_item(
    item_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    service_id: Optional[int] = Form(None),
    work_type: Optional[str] = Form(None),
    requester_name: Optional[str] = Form(None),
    assignee_id: Optional[int] = Form(None),
    estimate_hours: Optional[Decimal] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.title = title
        item.description = description
        item.service_id = service_id
        item.work_type = work_type
        item.requester_name = requester_name
        item.assignee_id = assignee_id
        item.estimate_hours = estimate_hours
        item.notes = notes
        db.commit()
    return RedirectResponse(url="/", status_code=303)
