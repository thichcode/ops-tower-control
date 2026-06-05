"""
Ops Control Tower CLI — terminal interface for daily ops.

Usage:
    python cli.py ls                    # List your items
    python cli.py ls --assignee 1       # List by assignee
    python cli.py add "Fix DNS"         # Quick add
    python cli.py add "Update backup" --service backup --hours 4
    python cli.py done 42               # Mark done
    python cli.py blocked 42 "Waiting"  # Mark blocked
    python cli.py dashboard             # Summary
    python cli.py triage                # What needs attention
"""

import argparse
import sys
from datetime import datetime, timezone
from app.database import SessionLocal
from app.models import WorkItem, User, Service


def cmd_ls(args):
    db = SessionLocal()
    try:
        query = db.query(WorkItem)
        if args.assignee:
            query = query.filter(WorkItem.assignee_id == args.assignee)
        if args.status:
            query = query.filter(WorkItem.status == args.status)
        items = query.order_by(WorkItem.created_at.desc()).all()
        if not items:
            print("No items found.")
            return
        for i in items:
            created = i.created_at.replace(tzinfo=timezone.utc) if i.created_at.tzinfo is None else i.created_at
            age = (datetime.now(timezone.utc) - created).days
            assignee = i.assignee.display_name if i.assignee else "-"
            print(f"#{i.id:<4} [{i.status:<8}] {i.title:<60} {assignee:<15} {age:3}d")
    finally:
        db.close()


def cmd_add(args):
    db = SessionLocal()
    try:
        svc = None
        if args.service:
            svc = db.query(Service).filter(Service.name.ilike(f"%{args.service}%")).first()
        item = WorkItem(
            title=args.title,
            description=args.desc,
            service_id=svc.id if svc else None,
            assignee_id=args.assignee,
            estimate_hours=args.hours,
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        print(f"Created #{item.id}: {item.title}")
    finally:
        db.close()


def cmd_done(args):
    db = SessionLocal()
    try:
        item = db.query(WorkItem).filter(WorkItem.id == args.id).first()
        if not item:
            print(f"Item #{args.id} not found")
            return
        item.status = "Done"
        item.completed_at = datetime.now(timezone.utc)
        db.commit()
        print(f"#{args.id} marked Done: {item.title}")
    finally:
        db.close()


def cmd_blocked(args):
    db = SessionLocal()
    try:
        item = db.query(WorkItem).filter(WorkItem.id == args.id).first()
        if not item:
            print(f"Item #{args.id} not found")
            return
        item.status = "Blocked"
        item.blocked_reason = args.reason or "No reason given"
        db.commit()
        print(f"#{args.id} marked Blocked: {item.title}")
    finally:
        db.close()


def cmd_dashboard(args):
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        month = now.strftime("%Y-%m")
        year, m = month.split("-")

        total = db.query(WorkItem).count()
        open_items = db.query(WorkItem).filter(WorkItem.status == "Open").count()
        blocked = db.query(WorkItem).filter(WorkItem.status == "Blocked").count()
        done = db.query(WorkItem).filter(WorkItem.status == "Done").count()

        from sqlalchemy import func
        est = db.query(func.coalesce(func.sum(WorkItem.estimate_hours), 0)).scalar()
        act = db.query(func.coalesce(func.sum(WorkItem.actual_hours), 0)).scalar()

        stale = db.query(WorkItem).filter(
            WorkItem.status.in_(["Open", "Blocked"]),
            WorkItem.created_at < (now.replace(day=1) - __import__("datetime").timedelta(days=1)).replace(day=1),
        ).count()

        members = db.query(User).filter(User.is_active == True).count()

        print("=" * 60)
        print(f"  Ops Control Tower — {now.strftime('%Y-%m-%d %H:%M')}")
        print("=" * 60)
        print(f"  Total items : {total}")
        print(f"  Open        : {open_items}")
        print(f"  Blocked     : {blocked}")
        print(f"  Done        : {done}")
        print(f"  Est. hours  : {float(est or 0):.1f}")
        print(f"  Actual hours: {float(act or 0):.1f}")
        print(f"  Stale (>1m) : {stale}")
        print(f"  Members     : {members}")
        print("=" * 60)
    finally:
        db.close()


def cmd_triage(args):
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        from sqlalchemy import func, case

        critical_services = db.query(Service).filter(Service.name.in_(["Kubernetes", "Cloudflare", "Backup"])).all()
        critical_ids = [s.id for s in critical_services]

        items = db.query(WorkItem).filter(
            WorkItem.status.in_(["Open", "Blocked"])
        ).order_by(
            case((WorkItem.service_id.in_(critical_ids), 0), else_=1),
            WorkItem.created_at.asc(),
        ).limit(20).all()

        print(f"{'ID':<5} {'Status':<10} {'Age':<5} {'Critical':<10} {'Title':<50} {'Assignee':<15}")
        print("-" * 100)
        for i in items:
            created = i.created_at.replace(tzinfo=timezone.utc) if i.created_at.tzinfo is None else i.created_at
            age = (now - created).days
            critical = "YES" if i.service_id in critical_ids else ""
            assignee = i.assignee.display_name if i.assignee else "-"
            mark = ">>>" if (age > 7 or i.service_id in critical_ids) else "   "
            print(f"{mark} #{i.id:<3} {i.status:<10} {age:<5} {critical:<10} {i.title[:48]:<50} {assignee:<15}")
    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Ops Control Tower CLI")
    subparsers = parser.add_subparsers(dest="command")

    p_ls = subparsers.add_parser("ls", help="List work items")
    p_ls.add_argument("--assignee", type=int, help="Filter by assignee ID")
    p_ls.add_argument("--status", help="Filter by status (Open, Done, Blocked)")

    p_add = subparsers.add_parser("add", help="Quick add work item")
    p_add.add_argument("title", help="Item title")
    p_add.add_argument("--desc", help="Description")
    p_add.add_argument("--service", help="Service name (partial match)")
    p_add.add_argument("--assignee", type=int, help="Assignee ID")
    p_add.add_argument("--hours", type=float, help="Estimate hours")

    p_done = subparsers.add_parser("done", help="Mark item Done")
    p_done.add_argument("id", type=int, help="Item ID")

    p_blocked = subparsers.add_parser("blocked", help="Mark item Blocked")
    p_blocked.add_argument("id", type=int, help="Item ID")
    p_blocked.add_argument("reason", nargs="?", help="Block reason")

    subparsers.add_parser("dashboard", help="Show summary")
    subparsers.add_parser("triage", help="Show what needs attention")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    cmds = {
        "ls": cmd_ls,
        "add": cmd_add,
        "done": cmd_done,
        "blocked": cmd_blocked,
        "dashboard": cmd_dashboard,
        "triage": cmd_triage,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
