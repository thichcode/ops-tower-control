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

    alerts = []

    for s in scores:
        user = db.query(User).filter(User.id == s.user_id).first()
        name = user.display_name if user else f"User #{s.user_id}"

        if s.risk_level == "High" and s.flag_count >= 3:
            alerts.append({
                "type": "high_risk",
                "user_id": s.user_id,
                "member": name,
                "flags": s.flag_count,
                "detail": f"{name} has {s.flag_count} risk flags — High retention risk",
            })

        prev = db.query(RetentionScore).filter(
            RetentionScore.user_id == s.user_id,
            RetentionScore.month < month_key,
        ).order_by(RetentionScore.month.desc()).first()

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
        result = send_teams_card(
            webhook_url=TEAMS_ALERT_WEBHOOK,
            title=f"Retention Risk Alerts — {month_key}",
            summary=f"{len(alerts)} retention alerts",
            sections=sections,
            color="E81123",
        )
        return {"alerts": alerts, "send_result": result}

    return {"alerts": alerts}
