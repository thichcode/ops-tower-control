"""
SDP Sync Script — run via cron / task scheduler:
    python sync_sdp.py [--mock] [--dry-run]

Environment variables:
    SDP_API_URL=https://your-sdp-instance/api/v3
    SDP_API_KEY=your-api-key
"""

import argparse
from app.database import SessionLocal
from app.services.sdp_sync import sync_sdp_tickets

parser = argparse.ArgumentParser(description="Sync SDP tickets into Ops Control Tower")
parser.add_argument("--mock", action="store_true", help="Use mock data for testing")
parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
args = parser.parse_args()

db = SessionLocal()
try:
    stats = sync_sdp_tickets(db, mock=args.mock, dry_run=args.dry_run)
    print(f"SDP sync complete: {stats}")
finally:
    db.close()
