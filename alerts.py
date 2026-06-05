"""
Leader alerts — run via cron:
    python alerts.py [--dry-run]

Checks:
  - Stale items (> 14 days)
  - Over-utilization (> 120%)
  - Requester demand spike
  - Critical service load

Environment:
    TEAMS_ALERT_WEBHOOK_URL=https://your-webhook
"""

import argparse
from app.database import SessionLocal
from app.services.leader_alerts import send_leader_alerts

parser = argparse.ArgumentParser(description="Send leader alerts via Teams")
parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
args = parser.parse_args()

db = SessionLocal()
try:
    result = send_leader_alerts(db, dry_run=args.dry_run)
    print(f"Alerts: {result.get('message')}")
    for alert in result.get("alerts", []):
        print(f"  [{alert['type']}] count={alert['count']}")
    if args.dry_run:
        for sec in result.get("sections", []):
            print(f"  Section: {sec['title']}")
            for f in sec.get("facts", []):
                print(f"    {f['name']}: {f['value']}")
finally:
    db.close()
