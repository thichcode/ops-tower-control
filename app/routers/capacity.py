from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database import get_db
from app.models import Capacity, User
from app.templates import TemplateResponse

router = APIRouter(prefix="/capacity", tags=["capacity"])


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


@router.get("")
def list_capacity(request: Request, month: Optional[str] = None, db: Session = Depends(get_db)):
    month = month or _current_month()
    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()

    records = {}
    for c in db.query(Capacity).filter(Capacity.month == month).all():
        records[c.user_id] = c

    data = []
    for u in users:
        c = records.get(u.id)
        data.append({
            "user_id": u.id,
            "display_name": u.display_name,
            "capacity_hours": float(c.capacity_hours) if c else None,
            "leave_hours": float(c.leave_hours) if c else 0,
            "meeting_hours": float(c.meeting_hours) if c else 0,
            "notes": c.notes if c else "",
            "exists": c is not None,
        })

    return TemplateResponse("capacity.html", {
        "request": request,
        "data": data,
        "month": month,
    })


@router.post("/save")
def save_capacity(
    month: str = Form(...),
    db: Session = Depends(get_db),
    request: Request = None,
):
    form = request.form() if request else {}
    users = db.query(User).filter(User.is_active == True).all()
    return RedirectResponse(url=f"/capacity?month={month}", status_code=303)


@router.post("/{user_id}")
def set_capacity(
    user_id: int,
    month: str = Form(...),
    capacity_hours: Decimal = Form(...),
    leave_hours: Decimal = Form(0),
    meeting_hours: Decimal = Form(0),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    existing = db.query(Capacity).filter(
        Capacity.user_id == user_id,
        Capacity.month == month,
    ).first()

    try:
        with db.begin_nested():
            if existing:
                existing.capacity_hours = capacity_hours
                existing.leave_hours = leave_hours
                existing.meeting_hours = meeting_hours
                existing.notes = notes
            else:
                cap = Capacity(
                    user_id=user_id,
                    month=month,
                    capacity_hours=capacity_hours,
                    leave_hours=leave_hours,
                    meeting_hours=meeting_hours,
                    notes=notes,
                )
                db.add(cap)
    except IntegrityError:
        return RedirectResponse(url=f"/capacity?month={month}&error=duplicate", status_code=303)

    db.commit()
    return RedirectResponse(url=f"/capacity?month={month}", status_code=303)
