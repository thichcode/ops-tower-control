# 🏗️ Ops Control Tower

> **Lightweight Operations Control Tower** — privacy-preserving ops evidence collector. Capture invisible work, measure demand vs capacity, and show who is requesting work from your team — without scanning everyone's chats.

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
| Combine all sources (privacy-safe) | Member-controlled local helper + SDP + Zabbix + Manual — unified view |
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

### Services
Service catalog — manage active/inactive services, assign categories.

![Services](screenshots/services_catalog.png)

### Users 👥
User management — view all members, active/inactive status.

![Users](screenshots/users.png)

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

### Executive Summary 📊
One-glance situational view combining 4 critical leadership views in a 4-card grid: Retention high-risk members, Scorecard top/bottom 3, SLA breach items, and Stale critical services. 1-click navigation to detail pages.

![Executive Summary](screenshots/executive.png)

### Retention Risk 🧠
Anomaly detection dashboard — z-score analysis across 6 signals (leave, throughput, cycle time, utilization, blocked ratio, meetings) to identify members at risk of burnout or disengagement. High/Medium/Low risk levels with per-member detail breakdown.

![Retention Risk](screenshots/retention.png)

![Retention Detail](screenshots/retention_detail.png)

### Employee Scorecard 🏆
Quarterly/yearly scorecard ranking members across 7 criteria: Productivity, Efficiency, Reliability, Versatility, Improvement, Dedication, and Risk Improvement. CSV export available.

![Employee Scorecard](screenshots/performance.png)

### Reward Report 💰
Boss-facing Vietnamese CSV report for reward/recognition proposals. Top 3 → "🥇 Đề xuất khen thưởng", Bottom 3 → "Cần hỗ trợ thêm", with team avg baseline, Δ kỳ trước, top strengths, and standout task evidence. Includes signature lines for approval workflow.

![Reward Report](screenshots/reward_report.png)

### Member Intake 📥
Privacy-first intake: members use a local helper (`tools/member_helper.py`) to collect, filter, redact, and send evidence from Teams/email/SDP. Server never scans raw chats. Support for service alias resolution, identity matching, confidence scoring, secret redaction, and duplicate detection. Upload via web UI or direct API.

![Import](screenshots/import.png)

## 🧱 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.11+ / FastAPI |
| **Database** | PostgreSQL 15+ (SQLite for dev) |
| **ORM** | SQLAlchemy 2.0 |
| **Templates** | Jinja2 + Bootstrap 5 |
| **Migrations** | Alembic |
| **Container** | Docker + Docker Compose |

## 🚀 Deployment (Docker)

### Production (PostgreSQL + web)
```bash
cp .env.example .env
# Edit .env to set TEAMS_DIGEST_WEBHOOK and TEAMS_ALERT_WEBHOOK if needed
docker compose up -d
# Web: http://localhost:8080
```

Includes `web` (FastAPI) + `db` (PostgreSQL 16) services with healthchecks and persistent volumes.

### Dev (SQLite, no DB service)
```bash
docker compose --profile dev up -d web-dev
# Web: http://localhost:8080
```

### With Adminer (DB UI)
```bash
docker compose --profile tools up -d
# Adminer: http://localhost:8081 (login: opsdash / opsdash / db)
```

### Stop & cleanup
```bash
docker compose down           # stop, keep volumes
docker compose down -v        # stop + delete volumes (fresh start)
```

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
│   │   ├── intake.py          # Teams, SDP, Zabbix, member package intake APIs
│   │   ├── importer.py        # File upload (old format + member package)
│   │   ├── reviews.py         # AI review queue (optional)
│   │   ├── dashboards.py      # 8 dashboards (incl. executive summary) + CSV exports
│   │   ├── capacity.py        # Capacity management
│   │   ├── requester.py       # Requester status portal
│   │   ├── retention.py       # Retention risk dashboard
│   │   └── performance.py     # Employee scorecard + reward report
│   ├── services/
│   │   ├── parser.py          # Teams command parser
│   │   ├── member_intake.py   # Member package import (dedup, redact, confidence)
│   │   ├── intake_rules.py    # Service/identity aliases, confidence constants
│   │   ├── ai_review.py       # Opt-in AI classification review
│   │   ├── sdp_sync.py        # SDP ticket sync
│   │   ├── zabbix_sync.py     # Zabbix problem sync
│   │   ├── performance.py     # Scorecard computation
│   │   ├── retention.py       # Retention score computation
│   │   ├── retention_alerts.py # Retention risk alerts
│   │   ├── leader_alerts.py   # Utilization/stale/requester spike alerts
│   │   ├── daily_digest.py    # Daily Teams digest
│   │   ├── notifications.py   # Notification helpers
│   │   └── query_utils.py     # Shared query utilities
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
│       ├── requester_status.html
│       ├── retention.html
│       └── retention_detail.html
├── cli.py                     # Terminal UI (ops ls, add, done, blocked, dashboard)
├── tools/
│   └── member_helper.py       # Local CLI helper — collect/filter/redact/send packages
├── sync_sdp.py                # SDP sync script (cron)
├── sync_zabbix.py             # Zabbix sync script (cron)
├── seed.py                    # Demo data
├── retention_alerts.py        # Retention risk alert script (cron)
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
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

Open **http://localhost:8080** in your browser.

### Configuration

Set environment variables for production:

```bash
# PostgreSQL (defaults to SQLite for dev)
export DATABASE_URL="postgresql://user:pass@localhost:15432/opsdash"

# SDP integration
export SDP_API_URL="https://your-sdp/api/v3"
export SDP_API_KEY="your-key"

# Zabbix integration
export ZABBIX_API_URL="https://your-zabbix/api_jsonrpc.php"
export ZABBIX_API_TOKEN="your-token"
```

## 🔌 Integrations

### AI-assisted review

OpsDash can optionally ask OpenAI to review uncertain task classifications. AI suggestions are stored in a review queue with evidence, confidence, and rationale. They never change a work item automatically; a lead must approve or reject each proposal.

```bash
AI_REVIEW_ENABLED=true
AI_REVIEW_MODEL=gpt-5.5
OPENAI_API_KEY=your-key
```

Open `/reviews` to process the queue. Without an API key, the same workflow remains available with deterministic rule-based suggestions.

For Teams packages, messages sharing the same `thread_id` are attached as conversation evidence to one work item. New replies reopen the review workflow instead of automatically marking the task complete. Only redacted evidence stored in OpsDash is sent for AI review, and API responses are requested with storage disabled.

### Teams (Power Automate)

1. Create a Power Automate flow triggered on reply to channel message
2. Filter for replies containing `/task`
3. POST to `http://your-server/api/intake/teams`
4. See [full guide](docs/guides/power-automate-teams-intake.md)

```bash
# Test the Teams intake API
curl -X POST http://localhost:8080/api/intake/teams \
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
- [x] Retention Risk Prediction (z-score anomaly detection, dashboard, alerts)
- [ ] AI classifier (auto-classify service/type)
- [x] Daily Teams digest
- [x] Leader alerts (utilization > 120%, stale items, requester spikes)
- [x] Sprint 6 — Member-Controlled Intake (privacy-first local helper + server package API)
- [x] Intake Accuracy Rules (service aliases, identity aliases, confidence scoring)
- [x] Service catalog management
- [ ] Needs Review queue (UI for low-confidence items)
- [ ] Service Health (Zabbix + SDP + risk score)

## 📄 License

MIT

---

<p align="center">Built for Platform & Enterprise Applications Teams</p>
