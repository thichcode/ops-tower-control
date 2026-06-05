"""
Zabbix Sync Script — run via cron / task scheduler:
    python sync_zabbix.py [--mock] [--dry-run]

Environment variables:
    ZABBIX_API_URL=https://your-zabbix/api_jsonrpc.php
    ZABBIX_API_TOKEN=your-api-token
"""

import argparse
from app.database import SessionLocal
from app.services.zabbix_sync import sync_zabbix_problems

parser = argparse.ArgumentParser(description="Sync Zabbix problems into Ops Control Tower")
parser.add_argument("--mock", action="store_true", help="Use mock data for testing")
parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
args = parser.parse_args()

db = SessionLocal()
try:
    stats = sync_zabbix_problems(db, mock=args.mock, dry_run=args.dry_run)
    print(f"Zabbix sync complete: {stats}")
finally:
    db.close()
