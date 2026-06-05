from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import User, RetentionScore
from app.services.retention import compute_all_scores
from app.services.notifications import send_teams_card, TEAMS_ALERT_WEBHOOK


def check_retention_alerts(db, dry_run=False):
    compute_all_scores(db)

    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    scores = db.query(RetentionScore).filter(
        RetentionScore.month == month_key,
    ).all()

    user_ids = list(set(s.user_id for s in scores))
    user_map = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids)).all()}

    all_prev = db.query(RetentionScore).filter(
        RetentionScore.month < month_key,
    ).order_by(RetentionScore.month.desc()).all()
    prev_map = {}
    for s in all_prev:
        if s.user_id not in prev_map:
            prev_map[s.user_id] = s

    alerts = []

    for s in scores:
        user = user_map.get(s.user_id)
        name = user.display_name if user else f"User #{s.user_id}"

        if s.risk_level == "High" and s.flag_count >= 3:
            alerts.append({
                "type": "high_risk",
                "user_id": s.user_id,
                "member": name,
                "flags": s.flag_count,
                "detail": f"{name} has {s.flag_count} risk flags — High retention risk",
            })

        prev = prev_map.get(s.user_id)

        if prev and prev.risk_level == "Medium" and s.risk_level == "High":
            alerts.append({
                "type": "escalated",
                "user_id": s.user_id,
                "member": name,
                "flags": s.flag_count,
                "detail": f"{name} escalated from Medium to High risk ({s.flag_count} flags)",
            })

    if dry_run:
        return {"alerts": alerts}

    if alerts and TEAMS_ALERT_WEBHOOK:
        sections = [{
            "title": f"⚠️ {len(alerts)} Retention Alerts",
            "facts": [{"name": a["member"], "value": a["detail"]} for a in alerts],
        }]
        try:
            result = send_teams_card(
                webhook_url=TEAMS_ALERT_WEBHOOK,
                title=f"Retention Risk Alerts — {month_key}",
                summary=f"{len(alerts)} retention alerts",
                sections=sections,
                color="E81123",
            )
            return {"alerts": alerts, "send_result": result}
        except Exception as e:
            return {"alerts": alerts, "error": str(e)}

    return {"alerts": alerts}
