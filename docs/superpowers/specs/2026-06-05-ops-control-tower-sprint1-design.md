# Ops Control Tower — Sprint 1 Design

> **Version:** 1.0
> **Date:** 2026-06-05
> **Status:** Approved for implementation

## Architecture

FastAPI backend + PostgreSQL + Jinja2 templates + Bootstrap 5. No auth. No async workers. Server-side rendered HTML (no REST API for Sprint 1).

## Tech Stack

- Python 3.11+ / FastAPI
- SQLAlchemy async + Alembic
- PostgreSQL 15+ (SQLite fallback for dev)
- Jinja2 server-side templates
- Bootstrap 5 + vanilla JS

## Directory Structure

```
opsdash/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Settings
│   ├── database.py          # Engine + session
│   ├── models.py            # ORM models
│   ├── schemas.py           # Pydantic schemas
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── work_items.py    # Work item routes
│   │   ├── services.py      # Service catalog routes
│   │   └── users.py         # User management routes
│   └── templates/
│       ├── base.html        # Layout
│       ├── my_work.html     # My Work dashboard
│       ├── work_item_form.html  # Quick Add / Edit
│       ├── services.html    # Service catalog
│       └── users.html       # User management
├── migrations/              # Alembic
├── requirements.txt
└── seed.py                  # Demo data
```

## Database Schema

### users
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| display_name | TEXT | NOT NULL |
| email | TEXT | UNIQUE NOT NULL |
| role | TEXT | DEFAULT 'member' |
| is_active | BOOLEAN | DEFAULT TRUE |
| created_at | TIMESTAMP | |

### services
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| name | TEXT | UNIQUE NOT NULL |
| category | TEXT | nullable |
| status | TEXT | DEFAULT 'active' |
| created_at | TIMESTAMP | |

### work_items
| Column | Type | Notes |
|--------|------|-------|
| id | SERIAL PK | |
| title | TEXT | NOT NULL |
| description | TEXT | nullable |
| service_id | INT FK → services | nullable |
| work_type | TEXT | DEFAULT 'Other' |
| source | TEXT | DEFAULT 'Manual' |
| requester_name | TEXT | nullable |
| requester_email | TEXT | nullable |
| assignee_id | INT FK → users | nullable |
| status | TEXT | DEFAULT 'Open' |
| estimate_hours | NUMERIC(10,2) | nullable |
| actual_hours | NUMERIC(10,2) | nullable |
| blocked_reason | TEXT | nullable |
| notes | TEXT | nullable |
| created_at | TIMESTAMP | |
| completed_at | TIMESTAMP | nullable |

## Routes (HTML-rendered)

- `GET /` → My Work page (filterable table)
- `GET /work-items/new` → Quick Add form
- `POST /work-items` → Create work item
- `POST /work-items/{id}/done` → Done (1-click)
- `POST /work-items/{id}/blocked` → Blocked (1-click)
- `GET /work-items/{id}/edit` → Edit form (leader only concept but no auth check yet)
- `POST /work-items/{id}/edit` → Update work item
- `GET /services` → Service catalog
- `POST /services` → Create service
- `POST /services/{id}/delete` → Delete service
- `GET /users` → User management
- `POST /users` → Create user
- `POST /users/{id}/delete` → Delete user

## UI Pages

### My Work (`/`)
- Filter bar: status, date range, search
- Table: Title, Requester, Service, Source, Age, Status, Actions (Done/Blocked)
- Age coloring: yellow > 3d, red > 7d
- Quick Add button → modal/form

### Service Catalog (`/services`)
- Table: name, category, status
- Add / Delete

### User Management (`/users`)
- Table: display_name, email, role, is_active
- Add / Delete

## Seed Data

Users: Engineer A, B, C (member) + Lead A (leader)
Services: GitLab, Cloudflare, Kubernetes, Backup, SVN, Zabbix, SharePoint
Work items: 10 items with mix of statuses

## Out of Scope for Sprint 1

- Authentication / login
- Teams intake API
- SDP / Zabbix sync
- Capacity management
- Audit logs
- Dashboards (Top Requester, Workload, Demand vs Capacity)
- CSV export
