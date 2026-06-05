import os
import requests
from typing import Optional
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import WorkItem

SDP_API_URL = os.getenv("SDP_API_URL", "")
SDP_API_KEY = os.getenv("SDP_API_KEY", "")

SDP_STATUS_MAP = {
    "Open": "Open",
    "In Progress": "Open",
    "On Hold": "Blocked",
    "Resolved": "Done",
    "Closed": "Done",
    "Cancelled": "Cancelled",
}

SDP_TYPE_MAP = {
    "Incident": "Incident",
    "Service Request": "Request",
    "Change": "Project",
    "Problem": "Incident",
}


def fetch_sdp_tickets(mock: bool = False) -> list:
    if mock:
        return _mock_tickets()
    resp = requests.get(
        f"{SDP_API_URL}/api/v3/requests",
        headers={"Authorization": f"Bearer {SDP_API_KEY}"},
        params={"limit": 100, "sort_by": "created_time.desc"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])


def _mock_tickets() -> list:
    return [
        {
            "id": "SDP-1001",
            "subject": "User cannot access SharePoint",
            "description": "User reported access denied to SharePoint site collection",
            "status": {"name": "Open"},
            "request_type": {"name": "Incident"},
            "requester": {"name": "End User A", "email": "user.a@company.com"},
            "technician": {"name": "Engineer A", "email": "eng.a@company.com"},
            "created_time": {"display_value": "2026-06-04 10:00:00"},
        },
        {
            "id": "SDP-1002",
            "subject": "New GitLab project creation",
            "description": "Please create new GitLab project for team Alpha",
            "status": {"name": "In Progress"},
            "request_type": {"name": "Service Request"},
            "requester": {"name": "PM B", "email": "pm.b@company.com"},
            "technician": {"name": "Engineer B", "email": "eng.b@company.com"},
            "created_time": {"display_value": "2026-06-03 14:30:00"},
        },
        {
            "id": "SDP-1003",
            "subject": "Backup restore failed",
            "description": "Nightly backup restore job failed for server X",
            "status": {"name": "On Hold"},
            "request_type": {"name": "Incident"},
            "requester": {"name": "System Alert", "email": "alert@company.com"},
            "technician": {"name": "Engineer A", "email": "eng.a@company.com"},
            "created_time": {"display_value": "2026-06-01 08:00:00"},
        },
        {
            "id": "SDP-1004",
            "subject": "Cloudflare rate limit rule update",
            "description": "Update rate limiting rules for API endpoint",
            "status": {"name": "Resolved"},
            "request_type": {"name": "Change"},
            "requester": {"name": "Dev Team Lead", "email": "dev.lead@company.com"},
            "technician": {"name": "Engineer C", "email": "eng.c@company.com"},
            "created_time": {"display_value": "2026-05-28 09:00:00"},
        },
    ]


def map_sdp_ticket(ticket: dict) -> dict:
    status = SDP_STATUS_MAP.get(ticket.get("status", {}).get("name", "Open"), "Open")
    sdp_type = ticket.get("request_type", {}).get("name", "")
    work_type = SDP_TYPE_MAP.get(sdp_type, "Other")

    requester = ticket.get("requester", {}) or {}
    technician = ticket.get("technician", {}) or {}

    return {
        "title": ticket.get("subject", "SDP Ticket")[:500],
        "description": ticket.get("description", ""),
        "source": "SDP",
        "source_id": str(ticket.get("id", "")),
        "requester_name": requester.get("name", ""),
        "requester_email": requester.get("email", ""),
        "work_type": work_type,
        "status": status,
    }


def sync_sdp_tickets(db, mock: bool = False, dry_run: bool = False) -> dict:
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    try:
        tickets = fetch_sdp_tickets(mock=mock)
    except Exception as e:
        stats["errors"] = 1
        stats["error_msg"] = str(e)
        return stats

    for ticket in tickets:
        source_id = str(ticket.get("id", ""))
        if not source_id:
            stats["skipped"] += 1
            continue

        existing = db.query(WorkItem).filter(
            WorkItem.source == "SDP",
            WorkItem.source_id == source_id,
        ).first()

        mapped = map_sdp_ticket(ticket)

        if existing:
            for key, val in mapped.items():
                if key not in ("source_id", "source"):
                    setattr(existing, key, val)
            stats["updated"] += 1
        else:
            item = WorkItem(**mapped)
            db.add(item)
            stats["created"] += 1

        if existing or not dry_run:
            pass

    if not dry_run:
        db.commit()

    return stats
