import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.database import get_db
from app.models import WorkItem, User, Service, Capacity
from app.templates import TemplateResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _date_filter(query, months: Optional[int]):
    if months:
        since = datetime.now(timezone.utc).replace(day=1)
        query = query.filter(WorkItem.created_at >= since)
    return query


@router.get("/top-requesters")
def top_requesters(
    request: Request,
    months: Optional[int] = Query(None, description="Filter last N months"),
    db: Session = Depends(get_db),
):
    base = db.query(
        WorkItem.requester_name,
        func.count(WorkItem.id).label("total"),
        func.sum(case((WorkItem.status == "Open", 1), else_=0)).label("open_count"),
        func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done_count"),
        func.sum(case((WorkItem.status == "Blocked", 1), else_=0)).label("blocked_count"),
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("total_estimated"),
        func.coalesce(func.sum(WorkItem.actual_hours), 0).label("total_actual"),
    )

    if months:
        since = datetime.now(timezone.utc).replace(day=1)
        base = base.filter(WorkItem.created_at >= since)

    rows = base.group_by(WorkItem.requester_name).order_by(func.count(WorkItem.id).desc()).all()

    grand_total = sum(r.total for r in rows) if rows else 1
    data = []
    for r in rows:
        data.append({
            "requester": r.requester_name or "Unnamed",
            "open": int(r.open_count or 0),
            "done": int(r.done_count or 0),
            "blocked": int(r.blocked_count or 0),
            "total": int(r.total),
            "estimated": float(r.total_estimated or 0),
            "actual": float(r.total_actual or 0),
            "demand_pct": round(r.total / grand_total * 100, 1),
        })

    return TemplateResponse("dashboard_top_requesters.html", {
        "request": request,
        "data": data,
        "months": months,
    })


@router.get("/workload-by-member")
def workload_by_member(
    request: Request,
    months: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    base = db.query(
        User.display_name,
        func.count(WorkItem.id).label("total"),
        func.sum(case((WorkItem.status == "Open", 1), else_=0)).label("open_count"),
        func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done_count"),
        func.sum(case((WorkItem.status == "Blocked", 1), else_=0)).label("blocked_count"),
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("total_estimated"),
    ).outerjoin(WorkItem, User.id == WorkItem.assignee_id).filter(User.is_active == True)

    if months:
        since = datetime.now(timezone.utc).replace(day=1)
        base = base.filter(WorkItem.created_at >= since)

    rows = base.group_by(User.display_name).order_by(func.count(WorkItem.id).desc()).all()

    data = []
    for r in rows:
        data.append({
            "member": r.display_name,
            "open": int(r.open_count or 0),
            "done": int(r.done_count or 0),
            "blocked": int(r.blocked_count or 0),
            "total": int(r.total),
            "estimated": float(r.total_estimated or 0),
        })

    return TemplateResponse("dashboard_workload.html", {
        "request": request,
        "data": data,
        "months": months,
    })


@router.get("/work-by-service")
def work_by_service(
    request: Request,
    months: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    base = db.query(
        Service.name,
        func.count(WorkItem.id).label("total"),
        func.sum(case((WorkItem.status == "Open", 1), else_=0)).label("open_count"),
        func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done_count"),
        func.sum(case((WorkItem.status == "Blocked", 1), else_=0)).label("blocked_count"),
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("total_estimated"),
    ).outerjoin(WorkItem, Service.id == WorkItem.service_id).filter(Service.status == "active")

    if months:
        since = datetime.now(timezone.utc).replace(day=1)
        base = base.filter(WorkItem.created_at >= since)

    rows = base.group_by(Service.name).order_by(func.count(WorkItem.id).desc()).all()

    data = []
    for r in rows:
        data.append({
            "service": r.name,
            "open": int(r.open_count or 0),
            "done": int(r.done_count or 0),
            "blocked": int(r.blocked_count or 0),
            "total": int(r.total),
            "estimated": float(r.total_estimated or 0),
        })

    return TemplateResponse("dashboard_services.html", {
        "request": request,
        "data": data,
        "months": months,
    })


# --- CSV Export ---

@router.get("/demand-vs-capacity")
def demand_vs_capacity(
    request: Request,
    month: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    month = month or now.strftime("%Y-%m")
    year, m = month.split("-")
    from calendar import monthrange
    start_day = datetime(int(year), int(m), 1, tzinfo=timezone.utc)
    last_day = monthrange(int(year), int(m))[1]
    end_day = datetime(int(year), int(m), last_day, 23, 59, 59, tzinfo=timezone.utc)

    items = db.query(
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("total_estimated"),
        func.coalesce(func.sum(WorkItem.actual_hours), 0).label("total_actual"),
        func.count(WorkItem.id).label("total_items"),
    ).filter(
        WorkItem.created_at >= start_day,
        WorkItem.created_at <= end_day,
    ).first()

    capacities = db.query(
        func.coalesce(func.sum(Capacity.capacity_hours), 0).label("total_capacity"),
        func.coalesce(func.sum(Capacity.leave_hours), 0).label("total_leave"),
        func.coalesce(func.sum(Capacity.meeting_hours), 0).label("total_meeting"),
    ).filter(Capacity.month == month).first()

    total_estimated = float(items.total_estimated or 0)
    total_actual = float(items.total_actual or 0)
    total_capacity = float(capacities.total_capacity or 0)
    total_leave = float(capacities.total_leave or 0)
    total_meeting = float(capacities.total_meeting or 0)
    net_capacity = total_capacity - total_leave - total_meeting

    gap = net_capacity - total_estimated
    gap_pct = round(abs(gap) / net_capacity * 100, 1) if net_capacity > 0 else 0
    is_over = gap < 0

    members = []
    member_rows = db.query(
        User.display_name,
        User.id,
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("estimated"),
        func.coalesce(func.sum(WorkItem.actual_hours), 0).label("actual"),
        func.count(WorkItem.id).label("count"),
    ).outerjoin(WorkItem, User.id == WorkItem.assignee_id).filter(
        User.is_active == True,
        WorkItem.created_at >= start_day,
        WorkItem.created_at <= end_day,
    ).group_by(User.display_name, User.id).order_by(User.display_name).all()

    for row in member_rows:
        cap = db.query(Capacity).filter(
            Capacity.user_id == row.id,
            Capacity.month == month,
        ).first()
        member_cap = float(cap.capacity_hours) if cap and cap.capacity_hours else 0
        member_leave = float(cap.leave_hours) if cap and cap.leave_hours else 0
        member_meeting = float(cap.meeting_hours) if cap and cap.meeting_hours else 0
        member_net = member_cap - member_leave - member_meeting
        est = float(row.estimated or 0)
        members.append({
            "name": row.display_name,
            "estimated": est,
            "actual": float(row.actual or 0),
            "count": int(row.count),
            "capacity": member_net,
            "utilization_pct": round(est / member_net * 100, 1) if member_net > 0 else 0,
        })

    return TemplateResponse("dashboard_demand_vs_capacity.html", {
        "request": request,
        "month": month,
        "total_estimated": total_estimated,
        "total_actual": total_actual,
        "total_capacity": total_capacity,
        "total_leave": total_leave,
        "total_meeting": total_meeting,
        "net_capacity": net_capacity,
        "gap": abs(gap),
        "gap_pct": gap_pct,
        "is_over": is_over,
        "items_count": int(items.total_items or 0),
        "members": members,
    })


@router.get("/export/demand-vs-capacity")
def export_demand_vs_capacity(month: Optional[str] = Query(None), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    month = month or now.strftime("%Y-%m")
    year, m = month.split("-")
    from calendar import monthrange
    start_day = datetime(int(year), int(m), 1, tzinfo=timezone.utc)
    last_day = monthrange(int(year), int(m))[1]
    end_day = datetime(int(year), int(m), last_day, 23, 59, 59, tzinfo=timezone.utc)

    capacities = db.query(
        func.coalesce(func.sum(Capacity.capacity_hours), 0).label("total_capacity")
    ).filter(Capacity.month == month).first()
    total_cap = float(capacities.total_capacity or 0)

    items = db.query(
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("total_estimated")
    ).filter(
        WorkItem.created_at >= start_day,
        WorkItem.created_at <= end_day,
    ).first()
    total_est = float(items.total_estimated or 0)

    gap = total_cap - total_est
    summary = [
        ["Metric", "Value"],
        ["Month", month],
        ["Total Capacity", total_cap],
        ["Total Estimated Demand", total_est],
        ["Gap", gap],
        ["Gap %", f"{round(abs(gap)/total_cap*100,1) if total_cap > 0 else 0}%"],
    ]

    return _csv_response("demand-vs-capacity.csv", [], summary)


def _csv_response(filename: str, headers: list, rows: list):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for row in rows:
        w.writerow(row)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/top-requesters")
def export_top_requesters(months: Optional[int] = Query(None), db: Session = Depends(get_db)):
    base = db.query(
        WorkItem.requester_name,
        func.count(WorkItem.id).label("total"),
        func.sum(case((WorkItem.status == "Open", 1), else_=0)).label("open"),
        func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done"),
        func.sum(case((WorkItem.status == "Blocked", 1), else_=0)).label("blocked"),
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("estimated"),
        func.coalesce(func.sum(WorkItem.actual_hours), 0).label("actual"),
    )
    if months:
        since = datetime.now(timezone.utc).replace(day=1)
        base = base.filter(WorkItem.created_at >= since)
    rows = base.group_by(WorkItem.requester_name).order_by(func.count(WorkItem.id).desc()).all()

    return _csv_response(
        "top-requesters.csv",
        ["Requester", "Total", "Open", "Done", "Blocked", "Estimated Hours", "Actual Hours"],
        [[r.requester_name or "Unnamed", int(r.total), int(r.open or 0), int(r.done or 0), int(r.blocked or 0), float(r.estimated or 0), float(r.actual or 0)] for r in rows],
    )


@router.get("/export/workload-by-member")
def export_workload(months: Optional[int] = Query(None), db: Session = Depends(get_db)):
    base = db.query(
        User.display_name,
        func.count(WorkItem.id).label("total"),
        func.sum(case((WorkItem.status == "Open", 1), else_=0)).label("open"),
        func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done"),
        func.sum(case((WorkItem.status == "Blocked", 1), else_=0)).label("blocked"),
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("estimated"),
    ).outerjoin(WorkItem, User.id == WorkItem.assignee_id).filter(User.is_active == True)
    if months:
        since = datetime.now(timezone.utc).replace(day=1)
        base = base.filter(WorkItem.created_at >= since)
    rows = base.group_by(User.display_name).order_by(func.count(WorkItem.id).desc()).all()

    return _csv_response(
        "workload-by-member.csv",
        ["Member", "Total", "Open", "Done", "Blocked", "Estimated Hours"],
        [[r.display_name, int(r.total), int(r.open or 0), int(r.done or 0), int(r.blocked or 0), float(r.estimated or 0)] for r in rows],
    )


@router.get("/export/work-by-service")
def export_services(months: Optional[int] = Query(None), db: Session = Depends(get_db)):
    base = db.query(
        Service.name,
        func.count(WorkItem.id).label("total"),
        func.sum(case((WorkItem.status == "Open", 1), else_=0)).label("open"),
        func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done"),
        func.sum(case((WorkItem.status == "Blocked", 1), else_=0)).label("blocked"),
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("estimated"),
    ).outerjoin(WorkItem, Service.id == WorkItem.service_id).filter(Service.status == "active")
    if months:
        since = datetime.now(timezone.utc).replace(day=1)
        base = base.filter(WorkItem.created_at >= since)
    rows = base.group_by(Service.name).order_by(func.count(WorkItem.id).desc()).all()

    return _csv_response(
        "work-by-service.csv",
        ["Service", "Total", "Open", "Done", "Blocked", "Estimated Hours"],
        [[r.name, int(r.total), int(r.open or 0), int(r.done or 0), int(r.blocked or 0), float(r.estimated or 0)] for r in rows],
    )
