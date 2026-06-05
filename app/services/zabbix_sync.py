import os
import requests
from typing import Optional
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import WorkItem, Service

ZABBIX_API_URL = os.getenv("ZABBIX_API_URL", "")
ZABBIX_API_TOKEN = os.getenv("ZABBIX_API_TOKEN", "")

SEVERITY_MAP = {
    0: "Not classified",
    1: "Information",
    2: "Warning",
    3: "Average",
    4: "High",
    5: "Disaster",
}

WORK_TYPE_MAP = {
    0: "Other",
    1: "Incident",
    2: "Incident",
    3: "Incident",
    4: "Incident",
    5: "Incident",
}


def _zabbix_api_call(method: str, params: dict) -> dict:
    payload = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1,
    }
    headers = {"Content-Type": "application/json-rpc"}
    if ZABBIX_API_TOKEN:
        payload["auth"] = ZABBIX_API_TOKEN

    resp = requests.post(ZABBIX_API_URL, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_zabbix_problems(mock: bool = False) -> list:
    if mock:
        return _mock_problems()

    result = _zabbix_api_call("problem.get", {
        "output": "extend",
        "sortfield": ["eventid"],
        "sortorder": "DESC",
        "limit": 100,
        "selectAcknowledges": "extend",
        "selectTags": "extend",
    })
    return result.get("result", [])


def _mock_problems() -> list:
    return [
        {
            "eventid": "12345",
            "name": "CPU utilization > 90% on prod-web-01",
            "severity": "4",
            "clock": "1717488000",
            "hosts": [{"hostid": "1001", "name": "prod-web-01"}],
        },
        {
            "eventid": "12346",
            "name": "Disk space > 85% on db-master",
            "severity": "3",
            "clock": "1717401600",
            "hosts": [{"hostid": "1002", "name": "db-master"}],
        },
        {
            "eventid": "12347",
            "name": "Service httpd is down on app-01",
            "severity": "5",
            "clock": "1717315200",
            "hosts": [{"hostid": "1003", "name": "app-01"}],
        },
    ]


def fetch_zabbix_hostgroups(mock: bool = False) -> dict:
    if mock:
        return {"1001": "Kubernetes", "1002": "Backup", "1003": "Internal Web"}
    result = _zabbix_api_call("hostgroup.get", {
        "output": "extend",
        "selectHosts": ["hostid", "name"],
    })
    mapping = {}
    for group in result.get("result", []):
        for host in group.get("hosts", []):
            mapping[host["hostid"]] = group["name"]
    return mapping


def map_zabbix_problem(problem: dict, hostgroup_map: dict = None) -> dict:
    severity = int(problem.get("severity", 0))
    hostname = ""
    hostid = ""
    hosts = problem.get("hosts", [])
    if hosts:
        hostname = hosts[0].get("name", "")
        hostid = str(hosts[0].get("hostid", ""))

    service_hint = None
    if hostgroup_map and hostid in hostgroup_map:
        service_hint = hostgroup_map[hostid]

    return {
        "title": problem.get("name", "Zabbix Problem")[:500],
        "description": f"Severity: {SEVERITY_MAP.get(severity, 'Unknown')}\nHost: {hostname}\nEvent ID: {problem.get('eventid', '')}",
        "source": "Zabbix",
        "source_id": str(problem.get("eventid", "")),
        "source_url": f"{ZABBIX_API_URL}/tr_events.php?eventid={problem.get('eventid', '')}",
        "work_type": WORK_TYPE_MAP.get(severity, "Other"),
        "status": "Open",
        "notes": f"Zabbix severity: {severity} ({SEVERITY_MAP.get(severity, 'Unknown')})",
    }


def sync_zabbix_problems(db, mock: bool = False, dry_run: bool = False) -> dict:
    stats = {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

    try:
        problems = fetch_zabbix_problems(mock=mock)
        if not mock:
            hostgroup_map = fetch_zabbix_hostgroups(mock=False)
        else:
            hostgroup_map = fetch_zabbix_hostgroups(mock=True)
    except Exception as e:
        stats["errors"] = 1
        stats["error_msg"] = str(e)
        return stats

    for problem in problems:
        source_id = str(problem.get("eventid", ""))
        if not source_id:
            stats["skipped"] += 1
            continue

        existing = db.query(WorkItem).filter(
            WorkItem.source == "Zabbix",
            WorkItem.source_id == source_id,
        ).first()

        mapped = map_zabbix_problem(problem, hostgroup_map)

        # Try to match service
        hostname = ""
        hosts = problem.get("hosts", [])
        if hosts:
            hostname = hosts[0].get("name", "")
        hostgroup_name = hostgroup_map.get(str(hosts[0].get("hostid", ""))) if hosts else None
        if hostgroup_name:
            svc = db.query(Service).filter(
                Service.name.ilike(f"%{hostgroup_name}%")
            ).first()
            if svc:
                mapped["service_id"] = svc.id

        if existing:
            if existing.status == "Done" and mapped.get("status") == "Open":
                pass
            for key, val in mapped.items():
                if key not in ("source_id", "source", "source_url"):
                    setattr(existing, key, val)
            stats["updated"] += 1
        else:
            item = WorkItem(**mapped)
            db.add(item)
            stats["created"] += 1

    if not dry_run:
        db.commit()

    return stats
