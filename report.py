"""
Generate and send trend report to Teams.
Run via cron (e.g., every Monday):
    python report.py [--send]

Environment:
    TEAMS_DIGEST_WEBHOOK_URL=https://your-webhook
"""

import argparse
from datetime import datetime, timezone
from calendar import monthrange

from app.database import SessionLocal
from app.models import WorkItem
from app.services.notifications import send_teams_card, TEAMS_DIGEST_WEBHOOK
from sqlalchemy import func, case


def build_report(db):
    now = datetime.now(timezone.utc)
    rows = []
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
            func.count(WorkItem.id).label("total"),
            func.sum(case((WorkItem.status == "Done", 1), else_=0)).label("done"),
        ).filter(
            WorkItem.created_at >= start,
            WorkItem.created_at <= end,
        ).first()

        rows.append({
            "month": f"{y}-{m:02d}",
            "estimated": float(items.estimated or 0),
            "total": int(items.total or 0),
            "done": int(items.done or 0),
        })
    rows.reverse()
    return rows


def send_report(db, dry_run=False):
    rows = build_report(db)
    current = rows[-1] if rows else {}
    prev = rows[-2] if len(rows) > 1 else {}

    if prev.get("estimated", 0) > 0:
        demand_change = round((current.get("estimated", 0) - prev.get("estimated", 0)) / prev["estimated"] * 100, 1)
    else:
        demand_change = 0

    if prev.get("done", 0) > 0:
        throughput_change = round((current.get("done", 0) - prev.get("done", 0)) / prev["done"] * 100, 1)
    else:
        throughput_change = 0

    facts = [
        {"name": "Current month", "value": current.get("month", "-")},
        {"name": "Demand (est. hours)", "value": f"{current.get('estimated', 0):.1f}h ({demand_change:+.1f}% vs last month)"},
        {"name": "Throughput (items done)", "value": f"{current.get('done', 0)} items ({throughput_change:+.1f}% vs last month)"},
        {"name": "New items", "value": str(current.get("total", 0))},
    ]

    sections = [{
        "title": "Monthly Trend Summary",
        "facts": facts,
    }]

    month_rows = [f"{r['month']}: {r['done']} done, {r['estimated']:.0f}h demand" for r in rows[-3:]]
    sections.append({
        "title": "Last 3 Months",
        "text": "\n".join(month_rows),
    })

    if dry_run:
        print("=== Monthly Report (dry-run) ===")
        for f in facts:
            print(f"  {f['name']}: {f['value']}")
        return

    result = send_teams_card(
        webhook_url=TEAMS_DIGEST_WEBHOOK,
        title=f"Ops Monthly Report — {current.get('month', '')}",
        summary=f"Demand: {current.get('estimated', 0)}h | Throughput: {current.get('done', 0)} items",
        sections=sections,
        color="0078D7",
    )
    print(f"Report sent: {result}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate and send monthly trend report")
    parser.add_argument("--send", action="store_true", help="Actually send (default: dry-run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        send_report(db, dry_run=not args.send)
    finally:
        db.close()
