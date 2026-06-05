from app.database import SessionLocal, engine, Base
from app.models import User, Service, WorkItem, Capacity
from datetime import datetime, timezone, timedelta

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    users = [
        User(display_name="Engineer A", email="eng.a@company.com", role="member"),
        User(display_name="Engineer B", email="eng.b@company.com", role="member"),
        User(display_name="Engineer C", email="eng.c@company.com", role="member"),
        User(display_name="Lead A", email="lead.a@company.com", role="leader"),
    ]
    db.add_all(users)
    db.flush()

    services = [
        Service(name="GitLab", category="DevOps Platform"),
        Service(name="Cloudflare", category="Cloud & Edge"),
        Service(name="Kubernetes", category="DevOps Platform"),
        Service(name="Backup", category="Business Continuity"),
        Service(name="SVN", category="DevOps Platform"),
        Service(name="Zabbix", category="Observability"),
        Service(name="SharePoint", category="Collaboration"),
    ]
    db.add_all(services)
    db.flush()

    now = datetime.now(timezone.utc)
    items = [
        WorkItem(title="Fix Cloudflare DNS record for project ABC", requester_name="PM A", service_id=services[1].id, work_type="Incident", assignee_id=users[0].id, status="Open", created_at=now - timedelta(days=2)),
        WorkItem(title="Weekly backup restore test", requester_name="BA B", service_id=services[3].id, work_type="Request", assignee_id=users[1].id, status="Blocked", blocked_reason="Waiting for approval", created_at=now - timedelta(days=5)),
        WorkItem(title="Kubernetes node upgrade", requester_name="Manager C", service_id=services[2].id, work_type="Project", assignee_id=users[2].id, status="Done", completed_at=now - timedelta(days=1), created_at=now - timedelta(days=10)),
        WorkItem(title="GitLab CI runner maintenance", requester_name="Security Team", service_id=services[0].id, work_type="Improvement", assignee_id=users[0].id, status="Open", created_at=now - timedelta(days=1)),
        WorkItem(title="Audit Cloudflare WAF rules", requester_name="Audit Team", service_id=services[1].id, work_type="Audit", assignee_id=users[1].id, status="Open", created_at=now - timedelta(days=7)),
        WorkItem(title="SVN to Git migration planning", requester_name="PM A", service_id=services[4].id, work_type="Project", assignee_id=users[2].id, status="Open", created_at=now - timedelta(days=14)),
        WorkItem(title="Zabbix alert tuning for production", requester_name="Manager C", service_id=services[5].id, work_type="Improvement", assignee_id=users[0].id, status="Open", created_at=now - timedelta(days=3)),
        WorkItem(title="SharePoint permissions review", requester_name="BA B", service_id=services[6].id, work_type="Request", assignee_id=users[1].id, status="Open", created_at=now - timedelta(days=4)),
        WorkItem(title="PoC: New monitoring tool evaluation", requester_name="Lead A", work_type="PoC", assignee_id=users[2].id, status="Open", estimate_hours=16, created_at=now - timedelta(days=1)),
        WorkItem(title="Vendor meeting: Cloudflare Enterprise", requester_name="PM A", work_type="Meeting", assignee_id=users[0].id, status="Done", completed_at=now, created_at=now - timedelta(days=2)),
    ]
    db.add_all(items)
    db.flush()

    month = now.strftime("%Y-%m")
    capacities = [
        Capacity(user_id=users[0].id, month=month, capacity_hours=160, leave_hours=8, meeting_hours=12),
        Capacity(user_id=users[1].id, month=month, capacity_hours=160, leave_hours=0, meeting_hours=10),
        Capacity(user_id=users[2].id, month=month, capacity_hours=160, leave_hours=16, meeting_hours=8),
        Capacity(user_id=users[3].id, month=month, capacity_hours=160, leave_hours=0, meeting_hours=20),
    ]
    db.add_all(capacities)

    db.commit()
    print("Seed data created successfully!")
    print(f"  Users: {len(users)}")
    print(f"  Services: {len(services)}")
    print(f"  Work Items: {len(items)}")
    print(f"  Capacity records: {len(capacities)}")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
