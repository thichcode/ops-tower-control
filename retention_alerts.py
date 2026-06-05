import argparse
from app.database import SessionLocal
from app.services.retention_alerts import check_retention_alerts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check retention risk and send alerts")
    parser.add_argument("--send", action="store_true", help="Actually send (default: dry-run)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        result = check_retention_alerts(db, dry_run=not args.send)
        print(f"Retention check complete: {len(result['alerts'])} alerts")
        for a in result["alerts"]:
            print(f"  [{a['type']}] {a['detail']}")
    finally:
        db.close()
