from datetime import datetime, timezone
from calendar import monthrange
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, case, and_
from sqlalchemy.orm import Session

from app.models import User, WorkItem, Capacity, RetentionScore
from app.services.query_utils import average_cycle_days


@dataclass
class Period:
    type: str  # "quarter" or "year"
    year: int
    quarter: Optional[int] = None  # 1-4, None if year

    def label(self) -> str:
        if self.type == "quarter":
            return f"Q{self.quarter} {self.year}"
        return f"Year {self.year}"

    def key(self) -> str:
        if self.type == "quarter":
            return f"{self.year}-Q{self.quarter}"
        return f"{self.year}"

    def date_range(self):
        """Return (start_date, end_date) for this period."""
        if self.type == "quarter":
            start_month = (self.quarter - 1) * 3 + 1
            end_month = start_month + 2
            start = datetime(self.year, start_month, 1, tzinfo=timezone.utc)
            _, last = monthrange(self.year, end_month)
            end = datetime(self.year, end_month, last, 23, 59, 59, tzinfo=timezone.utc)
        else:
            start = datetime(self.year, 1, 1, tzinfo=timezone.utc)
            end = datetime(self.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return start, end

    def previous(self):
        """Return the previous period of same type."""
        if self.type == "quarter":
            q = self.quarter - 1
            y = self.year
            if q < 1:
                q = 4
                y -= 1
            return Period("quarter", y, q)
        return Period("year", self.year - 1)


def get_active_users(db: Session):
    return db.query(User).filter(User.is_active == True).all()


def count_done(db: Session, user_id: int, start, end):
    return db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
    ).scalar() or 0


def count_activity(db: Session, user_id: int, start, end):
    return db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0


def avg_cycle_time(db: Session, user_id: int, start, end):
    items = db.query(WorkItem.created_at, WorkItem.completed_at).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
    ).all()
    return average_cycle_days(items)


def reliability_score(db: Session, user_id: int, start, end):
    total = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    if total == 0:
        return 1.0
    blocked = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Blocked",
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    return 1.0 - (blocked / total)


def versatility_score(db: Session, user_id: int, start, end):
    types = db.query(func.count(func.distinct(WorkItem.work_type))).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    services = db.query(func.count(func.distinct(WorkItem.service_id))).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
        WorkItem.service_id.isnot(None),
    ).scalar() or 0
    return types + services


def dedication_score(db: Session, user_id: int, start, end):
    total_items = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0

    # Sum leave + meeting hours across months in period
    if start.year == end.year and start.month == end.month:
        months_in_period = [(start.year, start.month)]
    else:
        months_in_period = []
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            months_in_period.append((y, m))
            m += 1
            if m > 12:
                m = 1
                y += 1

    leave_total = 0.0
    meeting_total = 0.0
    for y, m in months_in_period:
        key = f"{y}-{m:02d}"
        cap = db.query(Capacity).filter(
            Capacity.user_id == user_id,
            Capacity.month == key,
        ).first()
        if cap:
            leave_total += float(cap.leave_hours or 0)
            meeting_total += float(cap.meeting_hours or 0)

    divisor = leave_total + meeting_total + 1
    return total_items / divisor


def improvement_score(db: Session, user_id: int, period: Period):
    current_start, current_end = period.date_range()
    current_done = count_done(db, user_id, current_start, current_end)

    prev = period.previous()
    prev_start, prev_end = prev.date_range()
    prev_done = count_done(db, user_id, prev_start, prev_end)

    if prev_done == 0:
        return 1.0 if current_done > 0 else 0.0
    return current_done / prev_done


def risk_improvement_score(db: Session, user_id: int, period: Period):
    """Return risk improvement points. Positive = improvement."""
    current_start, current_end = period.date_range()
    prev = period.previous()
    prev_start, prev_end = prev.date_range()

    current_scores = db.query(RetentionScore).filter(
        RetentionScore.user_id == user_id,
        RetentionScore.created_at >= current_start,
        RetentionScore.created_at <= current_end,
    ).order_by(RetentionScore.created_at.desc()).all()

    prev_scores = db.query(RetentionScore).filter(
        RetentionScore.user_id == user_id,
        RetentionScore.created_at >= prev_start,
        RetentionScore.created_at <= prev_end,
    ).order_by(RetentionScore.created_at.desc()).all()

    risk_values = {"Low": 0, "Medium": 1, "High": 2}
    current_risk = risk_values.get(current_scores[0].risk_level, 0) if current_scores else 0
    prev_risk = risk_values.get(prev_scores[0].risk_level, 0) if prev_scores else 0

    improvement = prev_risk - current_risk  # positive = getting better
    return improvement


def compute_metrics(db: Session, user: User, period: Period):
    start, end = period.date_range()
    return {
        "evidence_count": count_activity(db, user.id, start, end),
        "productivity": count_done(db, user.id, start, end),
        "efficiency": avg_cycle_time(db, user.id, start, end),
        "reliability": reliability_score(db, user.id, start, end),
        "versatility": versatility_score(db, user.id, start, end),
        "improvement": improvement_score(db, user.id, period),
        "dedication": dedication_score(db, user.id, start, end),
        "risk_improvement": risk_improvement_score(db, user.id, period),
    }


METRIC_CONFIG = {
    "productivity": {"lower_better": False, "label": "Productivity"},
    "efficiency": {"lower_better": True, "label": "Efficiency"},
    "reliability": {"lower_better": False, "label": "Reliability"},
    "versatility": {"lower_better": False, "label": "Versatility"},
    "improvement": {"lower_better": False, "label": "Improvement"},
    "dedication": {"lower_better": False, "label": "Dedication"},
    "risk_improvement": {"lower_better": False, "label": "Risk Improvement"},
}


def rank_metric(values: list, lower_better: bool):
    """Rank a list of (user_id, value) tuples. Returns dict of user_id -> rank."""
    sorted_vals = sorted(values, key=lambda x: x[1], reverse=not lower_better)
    ranks = {}
    current_rank = 1
    for i, (uid, val) in enumerate(sorted_vals):
        if i > 0 and val != sorted_vals[i - 1][1]:
            current_rank = i + 1
        ranks[uid] = current_rank
    return ranks


def compute_performance(db: Session, period: Period):
    users = get_active_users(db)
    if not users:
        return []

    # Compute metrics for all users
    all_metrics = {}
    for user in users:
        all_metrics[user.id] = {
            "user": user,
            "metrics": compute_metrics(db, user, period),
        }

    # Rank each metric
    metric_ranks = {}
    for metric_name, config in METRIC_CONFIG.items():
        values = []
        for uid, member in all_metrics.items():
            metric_value = member["metrics"][metric_name]
            if member["metrics"]["evidence_count"] == 0:
                metric_value = float("inf") if config["lower_better"] else float("-inf")
            values.append((uid, metric_value))
        metric_ranks[metric_name] = rank_metric(values, config["lower_better"])

    # Build results
    results = []
    for uid, m in all_metrics.items():
        ranks = {name: metric_ranks[name][uid] for name in METRIC_CONFIG}
        overall = sum(ranks.values())
        results.append({
            "user": m["user"],
            "values": m["metrics"],
            "ranks": ranks,
            "overall_score": overall,
        })

    # Sort by overall score (lower = better), tiebreak by productivity rank
    results.sort(key=lambda r: (r["overall_score"], r["ranks"]["productivity"]))

    # Assign overall rank
    for i, r in enumerate(results):
        r["overall_rank"] = i + 1

    return results


def get_available_periods(db: Session) -> list[Period]:
    """Detect periods that have work item data."""
    first = db.query(func.min(WorkItem.created_at)).scalar()
    if not first:
        return [Period("quarter", datetime.now(timezone.utc).year, 1)]

    fy = first.year
    now = datetime.now(timezone.utc)
    ny = now.year
    current_quarter = (now.month - 1) // 3 + 1
    periods = []
    for y in range(fy, ny + 1):
        periods.append(Period("year", y))
        quarter_limit = current_quarter if y == ny else 4
        for q in range(1, quarter_limit + 1):
            periods.append(Period("quarter", y, q))
    return periods
