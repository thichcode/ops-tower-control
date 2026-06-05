# 🏗️ Ops Control Tower

> **Lightweight Operations Control Tower** — capture invisible work, measure demand vs capacity, and show who is requesting work from your team.

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python)](https://python.org)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-4169E1?logo=postgresql)](https://postgresql.org)
[![Bootstrap](https://img.shields.io/badge/Bootstrap-5.3-7952B3?logo=bootstrap)](https://getbootstrap.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 The Problem

Your team operates multiple enterprise platforms — ServiceDesk, GitLab, Kubernetes, Cloudflare, Zabbix, Backup, and more. Work comes from everywhere: SDP tickets, Teams messages, emails, meetings, and verbal requests. A large portion of real work is **invisible** in the ticketing system.

**Ops Control Tower** doesn't replace your existing tools. It captures the invisible work, measures demand vs capacity, and gives you management-level evidence when demand exceeds team capacity.

## 🎯 Objectives

| Goal | How |
|------|-----|
| Capture work with minimum effort | `/task` command in Teams or 1-click Quick Add |
| See who assigns the most work | Top Requester dashboard |
| Track workload by engineer | Workload by Member dashboard |
| Measure demand vs capacity | Demand vs Capacity dashboard |
| Track by service, type, source | Work by Service dashboard + filters |
| Combine all sources | Teams, SDP, Zabbix, Manual — unified view |
| Export reports | CSV export on every dashboard |

## 🖼️ Screenshots

### My Work
Filterable table — Quick Add, 1-click Done/Blocked. Age coloring: yellow > 3d, red > 7d.

![My Work](screenshots/mywork.png)

### Demand vs Capacity
Set monthly capacity per member. 4 KPI cards: Capacity, Demand, Gap, Utilization. Red alert when overloaded.

![Demand vs Capacity](screenshots/dvc.png)

### Top Requesters
Who assigns the most work? Open/Done/Blocked counts + estimated hours + demand %.

![Top Requesters](screenshots/requesters.png)

### Workload by Member
Who's overloaded? Open items per member. Yellow highlight > 3 open.

![Workload by Member](screenshots/workload.png)

### Work by Service
Which service consumes the most effort?

![Work by Service](screenshots/services_dash.png)

### Capacity Management
Set capacity / leave / meeting hours per member per month.

![Capacity Management](screenshots/capacity.png)

### Member Detail 👤
Per-member dashboard: KPI cards (Open/Blocked/Done), Demand vs Capacity for current month, cycle time, weekly throughput chart, WIP by service, and all their work items in one page.

![Member Detail](screenshots/member_detail.png)

### Trend Reports 📈
Monthly demand vs actual hours — bar chart showing 6-month trend with estimated vs actual hours and items done line.

![Trend Reports](screenshots/trends.png)

### Triage 🔥
"What's on fire" — items sorted by urgency: critical services first, oldest items first. Color-coded by age (red > 14d, yellow > 7d).

![Triage](screenshots/triage.png)

### KPI Metrics 📊
Throughput chart (weekly items done), WIP by member, average cycle time, SLA breach rate.

![KPI Metrics](screenshots/kpi.png)

### Requester Status Portal 🔍
Self-service check for requesters — enter your name to see the current status of all your work items without interrupting the team.

![Requester Status Portal](screenshots/requester.png)

## 🧱 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+ / FastAPI |
| **Database** | PostgreSQL 15+ (SQLite for dev) |
| **ORM** | SQLAlchemy 2.0 |
| **Templates** | Jinja2 + Bootstrap 5 |
| **Migrations** | Alembic |

## 📁 Project Structure

```
opsdash/
├── app/
│   ├── main.py                # FastAPI entry point
│   ├── config.py              # Settings
│   ├── database.py            # Engine + session
│   ├── models.py              # User, Service, WorkItem, Capacity
│   ├── schemas.py             # Pydantic schemas
│   ├── templates.py           # Jinja2 renderer
│   ├── routers/
│   │   ├── work_items.py      # My Work, CRUD, Done/Blocked
│   │   ├── services.py        # Service catalog
│   │   ├── users.py           # User management + member detail page
│   │   ├── intake.py          # Teams, SDP, Zabbix intake APIs
│   │   ├── dashboards.py      # 7 dashboards + CSV exports
│   │   ├── capacity.py        # Capacity management
│   │   └── requester.py       # Requester status portal
│   ├── services/
│   │   ├── parser.py          # Teams command parser
│   │   ├── sdp_sync.py        # SDP ticket sync
│   │   └── zabbix_sync.py     # Zabbix problem sync
│   └── templates/
│       ├── base.html
│       ├── my_work.html
│       ├── work_item_form.html
│       ├── services.html
│       ├── users.html
│       ├── capacity.html
│       ├── dashboard_*.html   # 7 dashboard templates
│       ├── member_detail.html
│       ├── dashboard_trends.html
│       ├── dashboard_kpi.html
│       ├── triage.html
│       └── requester_status.html
├── cli.py                     # Terminal UI (ops ls, add, done, blocked, dashboard)
├── sync_sdp.py                # SDP sync script (cron)
├── sync_zabbix.py             # Zabbix sync script (cron)
├── seed.py                    # Demo data
├── requirements.txt
└── docs/
    └── guides/
        └── power-automate-teams-intake.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL (or use SQLite for development)

### Setup

```bash
# Clone
git clone https://github.com/thichcode/ops-tower-control.git
cd ops-tower-control

# Install dependencies
pip install -r requirements.txt

# Seed demo data
python seed.py

# Run
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

### Configuration

Set environment variables for production:

```bash
# PostgreSQL (defaults to SQLite for dev)
export DATABASE_URL="postgresql://user:pass@localhost:5432/opsdash"

# SDP integration
export SDP_API_URL="https://your-sdp/api/v3"
export SDP_API_KEY="your-key"

# Zabbix integration
export ZABBIX_API_URL="https://your-zabbix/api_jsonrpc.php"
export ZABBIX_API_TOKEN="your-token"
```

## 🔌 Integrations

### Teams (Power Automate)

1. Create a Power Automate flow triggered on reply to channel message
2. Filter for replies containing `/task`
3. POST to `http://your-server/api/intake/teams`
4. See [full guide](docs/guides/power-automate-teams-intake.md)

```bash
# Test the Teams intake API
curl -X POST http://localhost:8000/api/intake/teams \
  -H "Content-Type: application/json" \
  -d '{
    "command": "/task 4h",
    "original_message_text": "Update firewall rules",
    "sender_name": "PM A",
    "sender_email": "pm.a@company.com",
    "assignee_email": "eng.a@company.com"
  }'
```

### SDP Sync

```bash
# Test with mock data
python sync_sdp.py --mock

# Production (requires SDP_API_URL + SDP_API_KEY)
python sync_sdp.py
```

### Zabbix Sync

```bash
# Test with mock data
python sync_zabbix.py --mock

# Production (requires ZABBIX_API_URL + ZABBIX_API_TOKEN)
python sync_zabbix.py
```

## 🔔 Notifications

### Daily Teams Digest
Sends a daily summary per member to Teams: open items, blocked items, items with no update > 3 days.

```bash
# Preview
python digest.py --dry-run

# Send (requires TEAMS_DIGEST_WEBHOOK_URL)
python digest.py
```

### Leader Alerts
Detects and alerts on:
- **Stale items** — open > 14 days
- **Over-utilization** — member demand > 120% capacity
- **Requester spikes** — requester opens 2x more items than last month
- **Critical service load** — high-priority services have 5+ open items

```bash
# Preview
python alerts.py --dry-run

# Send (requires TEAMS_ALERT_WEBHOOK_URL)
python alerts.py
```

### Schedule with Cron

```cron
# Every morning at 8:00
0 8 * * * cd /path/to/opsdash && python digest.py

# Every Monday at 9:00
0 9 * * 1 cd /path/to/opsdash && python alerts.py
```

## 🧪 Running Tests

```bash
# Inline test with FastAPI TestClient
python -c "
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
r = client.get('/')
print(r.status_code)
"
```

## 🗺️ Roadmap

- [x] Sprint 1 — Core data + Manual work
- [x] Sprint 2 — Teams Intake API
- [x] Sprint 3 — Dashboards + CSV Export
- [x] Sprint 4 — SDP + Zabbix Sync
- [x] Sprint 5 — Capacity + Demand vs Capacity
- [x] Member Detail page (per-member dashboard with KPIs, throughput, WIP, cycle time)
- [x] CLI tool (terminal UI — ls, add, done, blocked, dashboard)
- [x] Trend Reports dashboard (Chart.js, monthly trends)
- [x] Triage page ("What's on fire")
- [x] KPI Metrics dashboard (throughput, cycle time, WIP, SLA)
- [x] Requester Status Portal (public read-only)
- [x] Auto-report script (Teams monthly report)
- [ ] AI classifier (auto-classify service/type)
- [x] Daily Teams digest
- [x] Leader alerts (utilization > 120%, stale items, requester spikes)
- [ ] Service Health (Zabbix + SDP + risk score)

## 📄 License

MIT

---

<p align="center">Built for Platform & Enterprise Applications Teams</p>
