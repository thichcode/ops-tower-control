from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case

from app.models import WorkItem, User
from app.services.notifications import send_teams_card, TEAMS_DIGEST_WEBHOOK


DAYS_STALE = 3


def build_digest_data(db: Session) -> list:
    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(days=DAYS_STALE)

    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()
    result = []

    for user in users:
        items = db.query(WorkItem).filter(
            WorkItem.assignee_id == user.id
        ).all()

        open_items = [i for i in items if i.status == "Open"]
        blocked_items = [i for i in items if i.status == "Blocked"]
        stale_items = []
        for i in items:
            if i.status not in ("Open", "Blocked"):
                continue
            created = i.created_at.replace(tzinfo=timezone.utc) if i.created_at.tzinfo is None else i.created_at
            if created < stale_threshold:
                stale_items.append(i)

        if open_items or blocked_items:
            result.append({
                "name": user.display_name,
                "email": user.email,
                "open": len(open_items),
                "blocked": len(blocked_items),
                "stale": len(stale_items),
                "total_open": len(open_items) + len(blocked_items),
            })

    return result


def send_daily_digest(db: Session, dry_run: bool = False) -> dict:
    data = build_digest_data(db)
    total_open = sum(d["total_open"] for d in data)
    total_blocked = sum(d["blocked"] for d in data)
    total_stale = sum(d["stale"] for d in data)

    if not data:
        return {"message": "No open items — nothing to report", "data": []}

    sections = []
    for d in data:
        facts = [
            {"name": "Open", "value": str(d["open"])},
            {"name": "Blocked", "value": str(d["blocked"])},
        ]
        if d["stale"] > 0:
            facts.append({"name": f"No update >{DAYS_STALE}d", "value": str(d["stale"])})
        sections.append({
            "title": d["name"],
            "facts": facts,
        })

    if dry_run:
        return {
            "message": "Dry run — no message sent",
            "summary": f"{len(data)} members have open items",
            "sections": sections,
        }

    result = send_teams_card(
        webhook_url=TEAMS_DIGEST_WEBHOOK,
        title=f"Ops Daily Digest — {datetime.now().strftime('%Y-%m-%d')}",
        summary=f"Daily digest: {len(data)} members, {total_open} open, {total_blocked} blocked, {total_stale} stale",
        sections=sections,
        color="0078D7",
    )
    return {"message": "Digest sent", "members": len(data), "open": total_open, "blocked": total_blocked, "stale": total_stale, **result}
