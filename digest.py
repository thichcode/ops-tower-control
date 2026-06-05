"""
Daily Teams digest — run via cron:
    python digest.py [--dry-run]

Environment:
    TEAMS_DIGEST_WEBHOOK_URL=https://your-webhook
"""

import argparse
from app.database import SessionLocal
from app.services.daily_digest import send_daily_digest

parser = argparse.ArgumentParser(description="Send daily Teams digest")
parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
args = parser.parse_args()

db = SessionLocal()
try:
    result = send_daily_digest(db, dry_run=args.dry_run)
    print(f"Digest: {result.get('message')}")
    if "members" in result:
        print(f"  Members: {result['members']}, Open: {result['open']}, Blocked: {result['blocked']}, Stale: {result['stale']}")
    if args.dry_run:
        for sec in result.get("sections", []):
            print(f"  [{sec['title']}]")
            for f in sec.get("facts", []):
                print(f"    {f['name']}: {f['value']}")
finally:
    db.close()
