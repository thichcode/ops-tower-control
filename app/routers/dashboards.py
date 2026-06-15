import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_

from app.database import get_db
from app.models import WorkItem, User, Service, Capacity
from app.services.query_utils import average_cycle_days, month_key_bounds, months_ago_start
from app.templates import TemplateResponse

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _date_filter(query, months: Optional[int]):
    if months:
        query = query.filter(WorkItem.created_at >= months_ago_start(months))
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
        base = base.filter(WorkItem.created_at >= months_ago_start(months))

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
        User.id,
        User.display_name,
        func.count(WorkItem.id).label("total"),
        func.sum(case((WorkItem.status == "Open", 1), else_=0)).label("open_count"),
        func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done_count"),
        func.sum(case((WorkItem.status == "Blocked", 1), else_=0)).label("blocked_count"),
        func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("total_estimated"),
    )
    join_condition = User.id == WorkItem.assignee_id
    if months:
        join_condition = and_(join_condition, WorkItem.created_at >= months_ago_start(months))
    base = base.outerjoin(WorkItem, join_condition).filter(User.is_active == True)

    rows = base.group_by(User.id, User.display_name).order_by(func.count(WorkItem.id).desc()).all()

    data = []
    for r in rows:
        data.append({
            "member": r.display_name,
            "id": r.id,
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
    )
    join_condition = Service.id == WorkItem.service_id
    if months:
        join_condition = and_(join_condition, WorkItem.created_at >= months_ago_start(months))
    base = base.outerjoin(WorkItem, join_condition).filter(Service.status == "active")

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
    ).outerjoin(
        WorkItem,
        and_(
            User.id == WorkItem.assignee_id,
            WorkItem.created_at >= start_day,
            WorkItem.created_at <= end_day,
        ),
    ).filter(User.is_active == True).group_by(User.display_name, User.id).order_by(User.display_name).all()

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
        base = base.filter(WorkItem.created_at >= months_ago_start(months))
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
    )
    join_condition = User.id == WorkItem.assignee_id
    if months:
        join_condition = and_(join_condition, WorkItem.created_at >= months_ago_start(months))
    base = base.outerjoin(WorkItem, join_condition).filter(User.is_active == True)
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
    )
    join_condition = Service.id == WorkItem.service_id
    if months:
        join_condition = and_(join_condition, WorkItem.created_at >= months_ago_start(months))
    base = base.outerjoin(WorkItem, join_condition).filter(Service.status == "active")
    rows = base.group_by(Service.name).order_by(func.count(WorkItem.id).desc()).all()

    return _csv_response(
        "work-by-service.csv",
        ["Service", "Total", "Open", "Done", "Blocked", "Estimated Hours"],
        [[r.name, int(r.total), int(r.open or 0), int(r.done or 0), int(r.blocked or 0), float(r.estimated or 0)] for r in rows],
    )


@router.get("/trends")
def trends(request: Request, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    from calendar import monthrange

    months_data = []
    for i in range(6):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        start = datetime(y, m, 1, tzinfo=timezone.utc)
        _, last = monthrange(y, m)
        end = datetime(y, m, last, 23, 59, 59, tzinfo=timezone.utc)

        items = db.query(
            func.coalesce(func.sum(WorkItem.estimate_hours), 0).label("estimated"),
            func.coalesce(func.sum(WorkItem.actual_hours), 0).label("actual"),
            func.count(WorkItem.id).label("total"),
            func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done_count"),
        ).filter(
            WorkItem.created_at >= start,
            WorkItem.created_at <= end,
        ).first()

        months_data.append({
            "month": f"{y}-{m:02d}",
            "estimated": float(items.estimated or 0),
            "actual": float(items.actual or 0),
            "total": int(items.total or 0),
            "done": int(items.done_count or 0),
        })

    months_data.reverse()

    return TemplateResponse("dashboard_trends.html", {
        "request": request,
        "months": months_data,
    })


@router.get("/triage")
def triage(request: Request, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    critical_names = {"Kubernetes", "Cloudflare", "Backup"}
    critical_services = db.query(Service).filter(Service.name.in_(critical_names)).all()
    critical_ids = [s.id for s in critical_services]

    items = db.query(WorkItem).filter(
        WorkItem.status.in_(["Open", "Blocked"])
    ).order_by(
        case((WorkItem.service_id.in_(critical_ids), 0), else_=1),
        WorkItem.created_at.asc(),
    ).all()

    triage_items = []
    for i in items:
        created = i.created_at.replace(tzinfo=timezone.utc) if i.created_at.tzinfo is None else i.created_at
        age = (now - created).days
        is_critical = i.service_id in critical_ids
        svc_name = i.service.name if i.service else "-"
        triage_items.append({
            "id": i.id,
            "title": i.title,
            "status": i.status,
            "service": svc_name,
            "assignee": i.assignee.display_name if i.assignee else "-",
            "age": age,
            "is_critical": is_critical,
            "blocked_reason": i.blocked_reason,
        })

    return TemplateResponse("triage.html", {
        "request": request,
        "items": triage_items,
    })


@router.get("/kpi")
def kpi_metrics(request: Request, db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)

    # Throughput (items done per week, last 8 weeks)
    throughput = []
    for i in range(8):
        from datetime import timedelta
        w_end = now - timedelta(weeks=i)
        w_start = w_end - timedelta(weeks=1)
        done_count = db.query(func.count(WorkItem.id)).filter(
            WorkItem.status == "Done",
            WorkItem.completed_at >= w_start,
            WorkItem.completed_at <= w_end,
        ).scalar()
        throughput.append({
            "week": w_start.strftime("%m/%d"),
            "done": int(done_count or 0),
        })
    throughput.reverse()

    # Cycle time (avg days from created to completed for Done items)
    done_items = db.query(WorkItem.created_at, WorkItem.completed_at).filter(
        WorkItem.status == "Done",
        WorkItem.completed_at.isnot(None),
    ).all()
    cycle_time = round(average_cycle_days(done_items), 1)

    # WIP by member
    wip_members = db.query(
        User.display_name,
        func.count(WorkItem.id).label("wip"),
    ).outerjoin(WorkItem, User.id == WorkItem.assignee_id).filter(
        User.is_active == True,
        WorkItem.status == "Open",
    ).group_by(User.display_name).order_by(func.count(WorkItem.id).desc()).all()

    # SLA breach (items open > 7 days)
    from datetime import timedelta
    stale_threshold = now - timedelta(days=7)
    sla_breach = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.created_at < stale_threshold,
    ).scalar()

    total_active = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
    ).scalar() or 1

    sla_breach_rate = round(int(sla_breach or 0) / int(total_active) * 100, 1)

    return TemplateResponse("dashboard_kpi.html", {
        "request": request,
        "throughput": throughput,
        "cycle_time": cycle_time,
        "wip_members": [{"name": m.display_name, "wip": int(m.wip or 0)} for m in wip_members],
        "sla_breach": int(sla_breach or 0),
        "sla_breach_rate": sla_breach_rate,
        "total_active": int(total_active),
    })


@router.get("/executive")
def executive_summary(request: Request, db: Session = Depends(get_db)):
    from app.models import RetentionScore
    from app.services.performance import compute_performance, Period

    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")
    current_year = now.year
    current_quarter = (now.month - 1) // 3 + 1
    month_start, month_end = month_key_bounds(current_month)

    active_items = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
    ).scalar() or 0
    blocked_items = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status == "Blocked",
    ).scalar() or 0
    done_this_month = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status == "Done",
        WorkItem.completed_at >= month_start,
        WorkItem.completed_at <= month_end,
    ).scalar() or 0
    active_members = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    demand_hours = db.query(func.coalesce(func.sum(WorkItem.estimate_hours), 0)).filter(
        WorkItem.created_at >= month_start,
        WorkItem.created_at <= month_end,
    ).scalar() or 0
    capacity_row = db.query(
        func.coalesce(func.sum(Capacity.capacity_hours), 0).label("gross"),
        func.coalesce(func.sum(Capacity.leave_hours), 0).label("leave"),
        func.coalesce(func.sum(Capacity.meeting_hours), 0).label("meetings"),
    ).filter(Capacity.month == current_month).first()
    net_capacity = float(capacity_row.gross or 0) - float(capacity_row.leave or 0) - float(capacity_row.meetings or 0)
    utilization_pct = round(float(demand_hours) / net_capacity * 100, 1) if net_capacity > 0 else 0

    # Card 1: Retention high-risk (top 5 non-Low)
    retention_cards = db.query(RetentionScore).filter(
        RetentionScore.month == current_month,
        RetentionScore.risk_level != "Low",
    ).order_by(
        RetentionScore.flag_count.desc(),
    ).limit(5).all()

    retention_data = []
    for r in retention_cards:
        user = db.query(User).filter(User.id == r.user_id).first()
        signals = r.signals or {}
        flagged = []
        if signals.get("leave_z", 0) > 2:
            flagged.append(f"Leave {signals.get('leave_current', 0):.0f}h (z={signals.get('leave_z')})")
        if signals.get("throughput_z", 0) < -2:
            flagged.append(f"Throughput {signals.get('throughput_current')}/wk (z={signals.get('throughput_z')})")
        if signals.get("cycle_time_z", 0) > 2:
            flagged.append(f"Cycle {signals.get('cycle_time_current', 0):.1f}d (z={signals.get('cycle_time_z')})")
        if signals.get("utilization_pct", 0) > 100 or signals.get("utilization_pct", 0) < 30:
            flagged.append(f"Util {signals.get('utilization_pct', 0):.0f}%")
        if signals.get("meeting_z", 0) > 2:
            flagged.append(f"Meetings {signals.get('meeting_current', 0):.0f}h (z={signals.get('meeting_z')})")
        if signals.get("blocked_ratio_z", 0) > 2:
            flagged.append(f"Blocked {signals.get('blocked_ratio_current', 0)*100:.0f}%")
        retention_data.append({
            "user": user,
            "risk_level": r.risk_level,
            "flag_count": r.flag_count,
            "flagged_signals": flagged[:2],
        })

    # Card 2: Scorecard top/bottom 3
    period = Period("quarter", current_year, current_quarter)
    perf_results = compute_performance(db, period)
    eligible_perf = [result for result in perf_results if result["values"]["evidence_count"] > 0]
    scorecard_top = eligible_perf[:3]
    scorecard_bottom = perf_results[-3:] if len(perf_results) >= 3 else []

    # Card 3: SLA Breach (open > 30 days)
    from datetime import timedelta
    sla_threshold = now - timedelta(days=30)
    sla_items_query = db.query(WorkItem).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.created_at < sla_threshold,
    ).order_by(WorkItem.created_at.asc()).limit(5).all()

    total_active = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
    ).scalar() or 0
    sla_count = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.created_at < sla_threshold,
    ).scalar() or 0
    sla_rate = round(int(sla_count) / int(total_active) * 100, 1) if total_active > 0 else 0

    sla_items = []
    for item in sla_items_query:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        sla_items.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee.display_name if item.assignee else "Unassigned",
            "days_open": (now - created).days,
            "service": item.service.name if item.service else "-",
        })

    # Card 4: Stale Critical (oldest in Kubernetes/Cloudflare/Backup)
    critical_names = {"Kubernetes", "Cloudflare", "Backup"}
    critical_services = db.query(Service).filter(Service.name.in_(critical_names)).all()
    critical_ids = [s.id for s in critical_services]

    stale_items_query = db.query(WorkItem).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.service_id.in_(critical_ids),
    ).order_by(WorkItem.created_at.asc()).limit(5).all()

    stale_items = []
    for item in stale_items_query:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        stale_items.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee.display_name if item.assignee else "Unassigned",
            "days_open": (now - created).days,
            "service": item.service.name if item.service else "-",
        })

    attention_count = int(blocked_items) + int(sla_count) + len(retention_data)
    capacity_planned = net_capacity > 0
    if (not capacity_planned and float(demand_hours) > 0) or utilization_pct > 100 or sla_rate >= 20:
        operating_status = "At risk"
        operating_tone = "bad"
    elif utilization_pct >= 85 or attention_count > 0:
        operating_status = "Needs attention"
        operating_tone = "warn"
    else:
        operating_status = "On track"
        operating_tone = "good"

    return TemplateResponse("dashboard_executive.html", {
        "request": request,
        "retention_data": retention_data,
        "scorecard_top": scorecard_top,
        "scorecard_bottom": scorecard_bottom,
        "sla_items": sla_items,
        "sla_count": int(sla_count),
        "sla_rate": sla_rate,
        "total_active": int(total_active),
        "stale_items": stale_items,
        "current_month": current_month,
        "active_items": int(active_items),
        "blocked_items": int(blocked_items),
        "done_this_month": int(done_this_month),
        "active_members": int(active_members),
        "demand_hours": float(demand_hours),
        "net_capacity": net_capacity,
        "utilization_pct": utilization_pct,
        "attention_count": attention_count,
        "operating_status": operating_status,
        "operating_tone": operating_tone,
        "capacity_planned": capacity_planned,
    })
