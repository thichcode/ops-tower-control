from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.models import WorkItem, User, Service, Capacity
from app.services.notifications import send_teams_card, TEAMS_ALERT_WEBHOOK

STALE_DAYS = 14
UTILIZATION_THRESHOLD = 120


def check_stale_items(db: Session) -> list:
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=STALE_DAYS)

    items = db.query(WorkItem).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.created_at < threshold,
    ).order_by(WorkItem.created_at.asc()).limit(20).all()

    alerts = []
    for item in items:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        alerts.append({
            "id": item.id,
            "title": item.title[:80],
            "assignee": item.assignee.display_name if item.assignee else "Unassigned",
            "days_open": (now - created).days,
            "status": item.status,
        })
    return alerts


def check_utilization(db: Session) -> list:
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")

    members = db.query(User).filter(User.is_active == True).all()
    alerts = []

    for user in members:
        cap = db.query(Capacity).filter(
            Capacity.user_id == user.id,
            Capacity.month == month,
        ).first()
        if not cap or not cap.capacity_hours:
            continue

        net_cap = float(cap.capacity_hours) - float(cap.leave_hours or 0) - float(cap.meeting_hours or 0)
        if net_cap <= 0:
            continue

        estimated = db.query(func.coalesce(func.sum(WorkItem.estimate_hours), 0)).filter(
            WorkItem.assignee_id == user.id,
            WorkItem.created_at >= datetime(int(now.year), int(now.month), 1, tzinfo=timezone.utc),
        ).scalar()

        estimated = float(estimated or 0)
        utilization = round(estimated / net_cap * 100, 1) if net_cap > 0 else 0

        if utilization >= UTILIZATION_THRESHOLD:
            alerts.append({
                "name": user.display_name,
                "estimated": estimated,
                "capacity": net_cap,
                "utilization": utilization,
            })

    return alerts


def check_requester_spike(db: Session) -> list:
    now = datetime.now(timezone.utc)
    this_month = now.replace(day=1)
    last_month = (this_month - timedelta(days=1)).replace(day=1)

    this_count = db.query(
        WorkItem.requester_name,
        func.count(WorkItem.id).label("cnt"),
    ).filter(WorkItem.created_at >= this_month).group_by(WorkItem.requester_name).all()

    last_count = db.query(
        WorkItem.requester_name,
        func.count(WorkItem.id).label("cnt"),
    ).filter(
        WorkItem.created_at >= last_month,
        WorkItem.created_at < this_month,
    ).group_by(WorkItem.requester_name).all()

    last_map = {r.requester_name: r.cnt for r in last_count}
    alerts = []

    for r in this_count:
        if not r.requester_name:
            continue
        last = last_map.get(r.requester_name, 0)
        if last > 0 and r.cnt >= last * 2 and r.cnt >= 3:
            alerts.append({
                "requester": r.requester_name,
                "this_month": int(r.cnt),
                "last_month": int(last),
                "increase_pct": round((r.cnt - last) / last * 100, 0),
            })

    return alerts


def check_critical_service_load(db: Session) -> list:
    critical = db.query(Service).filter(
        Service.status == "active",
    ).all()

    alerts = []
    critical_names = {"Kubernetes", "Backup", "Cloudflare"}

    for svc in critical:
        if svc.name not in critical_names:
            continue
        open_count = db.query(func.count(WorkItem.id)).filter(
            WorkItem.service_id == svc.id,
            WorkItem.status == "Open",
        ).scalar()
        if open_count and int(open_count) >= 5:
            alerts.append({
                "service": svc.name,
                "open_count": int(open_count),
            })

    return alerts


def send_leader_alerts(db: Session, dry_run: bool = False) -> dict:
    alerts = []
    sections = []

    stale = check_stale_items(db)
    if stale:
        sections.append({
            "title": f"Stale Items (>{STALE_DAYS}d)",
            "facts": [{"name": f"#{s['id']} — {s['title']}", "value": f"{s['days_open']}d — {s['assignee']}"} for s in stale[:10]],
        })
        alerts.append({"type": "stale", "count": len(stale)})

    util = check_utilization(db)
    if util:
        sections.append({
            "title": f"Over-Utilization (>{UTILIZATION_THRESHOLD}%)",
            "facts": [{"name": u["name"], "value": f"{u['utilization']}% ({u['estimated']}h / {u['capacity']}h)"} for u in util],
        })
        alerts.append({"type": "utilization", "count": len(util)})

    spikes = check_requester_spike(db)
    if spikes:
        sections.append({
            "title": "Requester Demand Spike",
            "facts": [{"name": s["requester"], "value": f"{int(s['this_month'])} this month (↑{int(s['increase_pct'])}% vs last month)"} for s in spikes],
        })
        alerts.append({"type": "spike", "count": len(spikes)})

    critical = check_critical_service_load(db)
    if critical:
        sections.append({
            "title": "Critical Service Load",
            "facts": [{"name": c["service"], "value": f"{c['open_count']} open items"} for c in critical],
        })
        alerts.append({"type": "critical_service", "count": len(critical)})

    if not sections:
        return {"message": "No alerts triggered", "alerts": []}

    if dry_run:
        return {
            "message": "Dry run — no message sent",
            "alerts": alerts,
            "sections": sections,
        }

    result = send_teams_card(
        webhook_url=TEAMS_ALERT_WEBHOOK,
        title=f"Ops Leader Alert — {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        summary=f"{len(alerts)} alert types triggered",
        sections=sections,
        color="FF0000",
    )
    return {"message": "Alerts sent", "alerts": alerts, **result}
