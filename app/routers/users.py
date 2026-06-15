from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from datetime import datetime, timezone, timedelta

from app.database import get_db
from app.models import User, WorkItem, Capacity, Service
from app.services.query_utils import average_cycle_days, month_key_bounds
from app.templates import TemplateResponse

router = APIRouter()


@router.get("/users")
def list_users(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.display_name).all()
    return TemplateResponse("users.html", {"request": request, "users": users})


@router.get("/users/{user_id}")
def member_detail(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return TemplateResponse("users.html", {"request": request, "users": []})

    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    # Item counts
    open_count = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id, WorkItem.status == "Open"
    ).scalar() or 0
    blocked_count = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id, WorkItem.status == "Blocked"
    ).scalar() or 0
    done_count = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id, WorkItem.status == "Done"
    ).scalar() or 0
    total_count = open_count + blocked_count + done_count

    # Current month capacity
    cap = db.query(Capacity).filter(
        Capacity.user_id == user_id, Capacity.month == month_key
    ).first()
    capacity_hours = float(cap.capacity_hours or 0) if cap else 160
    leave_hours = float(cap.leave_hours or 0) if cap else 0
    meeting_hours = float(cap.meeting_hours or 0) if cap else 0
    available_hours = capacity_hours - leave_hours - meeting_hours

    # Current month demand
    month_start, month_end = month_key_bounds(month_key)
    demand = db.query(func.coalesce(func.sum(WorkItem.estimate_hours), 0)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= month_start,
        WorkItem.created_at <= month_end,
    ).scalar() or 0
    demand_hours = float(demand)

    # Utilization
    util_pct = round(demand_hours / available_hours * 100, 1) if available_hours > 0 else 0

    # Throughput (weekly done, last 8 weeks)
    throughput = []
    for i in range(8):
        w_end = now - timedelta(weeks=i)
        w_start = w_end - timedelta(weeks=1)
        done = db.query(func.count(WorkItem.id)).filter(
            WorkItem.assignee_id == user_id,
            WorkItem.status == "Done",
            WorkItem.completed_at >= w_start,
            WorkItem.completed_at <= w_end,
        ).scalar() or 0
        throughput.append({"week": w_start.strftime("%m/%d"), "done": int(done)})
    throughput.reverse()

    # Cycle time (avg days from created to completed)
    completed_items = db.query(WorkItem.created_at, WorkItem.completed_at).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at.isnot(None),
    ).all()
    cycle_time = round(average_cycle_days(completed_items), 1)

    # WIP by service
    wip_services = db.query(
        WorkItem.service_id,
        func.count(WorkItem.id).label("cnt"),
    ).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Open",
    ).group_by(WorkItem.service_id).order_by(func.count(WorkItem.id).desc()).all()

    svc_ids = [w.service_id for w in wip_services if w.service_id]
    svc_names = {}
    if svc_ids:
        for s in db.query(Service).filter(Service.id.in_(svc_ids)).all():
            svc_names[s.id] = s.name

    wip_svc_list = []
    for w in wip_services:
        name = svc_names.get(w.service_id, f"Service #{w.service_id}") if w.service_id else "Unassigned"
        wip_svc_list.append({"service": name, "count": int(w.cnt)})

    # Their work items
    items = db.query(WorkItem).filter(
        WorkItem.assignee_id == user_id
    ).order_by(
        case((WorkItem.status == "Open", 0), (WorkItem.status == "Blocked", 1), else_=2),
        WorkItem.created_at.desc(),
    ).all()

    for item in items:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        item.age_days = (now - created).days

    return TemplateResponse("member_detail.html", {
        "request": request,
        "member": user,
        "open_count": open_count,
        "blocked_count": blocked_count,
        "done_count": done_count,
        "total_count": total_count,
        "capacity_hours": capacity_hours,
        "available_hours": available_hours,
        "leave_hours": leave_hours,
        "meeting_hours": meeting_hours,
        "demand_hours": demand_hours,
        "util_pct": util_pct,
        "throughput": throughput,
        "cycle_time": cycle_time,
        "wip_services": wip_svc_list,
        "items": items,
        "month_key": month_key,
    })


@router.post("/users")
def create_user(
    display_name: str = Form(...),
    email: str = Form(...),
    role: str = Form("member"),
    db: Session = Depends(get_db),
):
    user = User(display_name=display_name, email=email, role=role)
    db.add(user)
    db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_active = False
        db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/{user_id}/activate")
def activate_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.is_active = True
        db.commit()
    return RedirectResponse(url="/users", status_code=303)
