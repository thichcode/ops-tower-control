import statistics
from datetime import datetime, timezone, timedelta
from typing import Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models import User, WorkItem, Capacity, RetentionScore
from app.services.query_utils import month_bounds


def compute_z_score(current_value, historical_values):
    if len(historical_values) < 2:
        return 0.0
    mean = statistics.mean(historical_values)
    stdev = statistics.stdev(historical_values)
    if stdev == 0:
        return 0.0
    return (current_value - mean) / stdev


def _month_key(year, month):
    return f"{year}-{month:02d}"


def get_historical_values(
    db: Session, user_id: int, field_getter, month_count: int = 6, now: Optional[datetime] = None
) -> list:
    if now is None:
        now = datetime.now(timezone.utc)
    values = []
    for i in range(1, month_count + 1):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        values.append(field_getter(db, user_id, y, m))
    return values


def get_leave_hours(db, user_id, year, month):
    cap = db.query(Capacity).filter(
        Capacity.user_id == user_id,
        Capacity.month == _month_key(year, month),
    ).first()
    return float(cap.leave_hours) if cap and cap.leave_hours else 0.0


def get_meeting_hours(db, user_id, year, month):
    cap = db.query(Capacity).filter(
        Capacity.user_id == user_id,
        Capacity.month == _month_key(year, month),
    ).first()
    return float(cap.meeting_hours) if cap and cap.meeting_hours else 0.0


def get_monthly_demand(db, user_id, year, month):
    start, end = month_bounds(year, month)
    result = db.query(func.coalesce(func.sum(WorkItem.estimate_hours), 0)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar()
    return float(result or 0)


def get_monthly_availability(db, user_id, year, month):
    cap = db.query(Capacity).filter(
        Capacity.user_id == user_id,
        Capacity.month == _month_key(year, month),
    ).first()
    capacity = float(cap.capacity_hours) if cap and cap.capacity_hours else 160.0
    leave = float(cap.leave_hours) if cap and cap.leave_hours else 0.0
    meetings = float(cap.meeting_hours) if cap and cap.meeting_hours else 0.0
    return capacity - leave - meetings


def get_cycle_time(db, user_id, year, month):
    start, end = month_bounds(year, month)
    items = db.query(WorkItem).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
        WorkItem.completed_at.isnot(None),
        WorkItem.created_at.isnot(None),
    ).all()
    if not items:
        return 0.0
    diffs = []
    for item in items:
        completed = item.completed_at.replace(tzinfo=timezone.utc) if item.completed_at.tzinfo is None else item.completed_at
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        diffs.append((completed - created).total_seconds() / 86400)
    return sum(diffs) / len(diffs)


def get_blocked_ratio(db, user_id, year, month):
    start, end = month_bounds(year, month)
    total = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    if total == 0:
        return 0.0
    blocked = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Blocked",
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    return blocked / total


def get_weekly_throughput(
    db: Session, user_id: int, now: Optional[datetime] = None
) -> tuple:
    if now is None:
        now = datetime.now(timezone.utc)
    recent = []
    prev = []
    for i in range(12):
        w_end = now - timedelta(weeks=i)
        w_start = w_end - timedelta(weeks=1)
        done = db.query(func.count(WorkItem.id)).filter(
            WorkItem.assignee_id == user_id,
            WorkItem.status == "Done",
            WorkItem.completed_at >= w_start,
            WorkItem.completed_at <= w_end,
        ).scalar() or 0
        if i < 4:
            recent.append(done)
        else:
            prev.append(done)
    recent_avg = statistics.mean(recent) if recent else 0
    prev_avg = statistics.mean(prev) if prev else 0
    return recent_avg, prev_avg, recent, prev


def compute_member_scores(db, user_id, now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    year = now.year
    month = now.month
    month_key = _month_key(year, month)

    current_leave = get_leave_hours(db, user_id, year, month)
    current_meetings = get_meeting_hours(db, user_id, year, month)
    current_cycle_time = get_cycle_time(db, user_id, year, month)
    current_blocked_ratio = get_blocked_ratio(db, user_id, year, month)
    recent_tp, prev_tp, recent_weekly, prev_weekly = get_weekly_throughput(db, user_id, now=now)

    historical_leave = get_historical_values(db, user_id, get_leave_hours, 6, now=now)
    historical_meetings = get_historical_values(db, user_id, get_meeting_hours, 6, now=now)

    def cycle_time_getter(db, user_id, y, m):
        return get_cycle_time(db, user_id, y, m)

    def blocked_ratio_getter(db, user_id, y, m):
        return get_blocked_ratio(db, user_id, y, m)

    def utilization_getter(db, user_id, y, m):
        demand = get_monthly_demand(db, user_id, y, m)
        avail = get_monthly_availability(db, user_id, y, m)
        if avail <= 0:
            return 0.0
        return (demand / avail) * 100

    utilization_pct = utilization_getter(db, user_id, year, month)
    historical_cycle_times = get_historical_values(db, user_id, cycle_time_getter, 3, now=now)
    historical_blocked_ratios = get_historical_values(db, user_id, blocked_ratio_getter, 3, now=now)
    historical_utilizations = get_historical_values(db, user_id, utilization_getter, 3, now=now)

    leave_z = compute_z_score(current_leave, historical_leave)
    meeting_z = compute_z_score(current_meetings, historical_meetings)
    throughput_z = compute_z_score(recent_tp, prev_weekly)
    cycle_time_z = compute_z_score(current_cycle_time, historical_cycle_times)
    utilization_z = compute_z_score(utilization_pct, historical_utilizations)
    blocked_ratio_z = compute_z_score(current_blocked_ratio, historical_blocked_ratios)

    flags = 0
    if leave_z > 2:
        flags += 1
    if throughput_z < -2:
        flags += 1
    if cycle_time_z > 2:
        flags += 1
    if utilization_pct > 100 or utilization_pct < 30 or abs(utilization_z) > 2:
        flags += 1
    if blocked_ratio_z > 2:
        flags += 1
    if meeting_z > 2:
        flags += 1

    if flags >= 3:
        risk_level = "High"
    elif flags >= 2:
        risk_level = "Medium"
    else:
        risk_level = "Low"

    signals = {
        "leave_current": current_leave,
        "leave_z": round(leave_z, 2),
        "meeting_current": current_meetings,
        "meeting_z": round(meeting_z, 2),
        "throughput_current": round(recent_tp, 1),
        "throughput_previous": round(prev_tp, 1),
        "throughput_z": round(throughput_z, 2),
        "cycle_time_current": current_cycle_time,
        "cycle_time_z": round(cycle_time_z, 2),
        "utilization_pct": round(utilization_pct, 2),
        "utilization_z": round(utilization_z, 2),
        "blocked_ratio_current": round(current_blocked_ratio, 4),
        "blocked_ratio_z": round(blocked_ratio_z, 2),
    }

    return {
        "user_id": user_id,
        "month": month_key,
        "risk_level": risk_level,
        "flag_count": flags,
        "signals": signals,
    }


def compute_all_scores(db):
    users = db.query(User).filter(User.is_active == True).all()
    now = datetime.now(timezone.utc)
    month_key = _month_key(now.year, now.month)

    for user in users:
        scores = compute_member_scores(db, user.id, now)

        existing = db.query(RetentionScore).filter(
            RetentionScore.user_id == user.id,
            RetentionScore.month == month_key,
        ).first()

        if existing:
            existing.risk_level = scores["risk_level"]
            existing.flag_count = scores["flag_count"]
            existing.signals = scores["signals"]
        else:
            record = RetentionScore(
                user_id=user.id,
                month=month_key,
                risk_level=scores["risk_level"],
                flag_count=scores["flag_count"],
                signals=scores["signals"],
            )
            db.add(record)

    db.commit()
