# Executive Summary Dashboard Design

## Overview
Single-page "Command Center" at `/dashboard/executive` combining 4 critical leadership views into a 4-card grid for 1-click situational awareness.

## Requirements
- **Goal**: Leader sees retention risks, performance extremes, SLA breaches, stale critical items in one glance (<5s)
- **Layout**: 4 equal-width cards in single row (desktop), stacked (mobile)
- **Data**: Reuse existing services/models — no new DB tables
- **Navigation**: Click items → existing detail pages
- **Performance**: Server-side render, <200ms target

---

## Route
```
GET /dashboard/executive
```
Registered in `app/routers/dashboards.py` with `@router.get("/executive")`

---

## Layout Structure

### Card 1: Retention High Risk
**Source**: `RetentionScore` table (pre-computed by `compute_all_scores()`)
**Query**: Current month, `risk_level != 'Low'`, order by `flag_count DESC`, limit 5
**Display per item**:
- Member name + risk badge (High=🔴, Medium=🟡)
- Flag count
- Top 2 flagged signals with z-scores (e.g., "Leave 24h (z=2.3)", "Throughput 1.2/wk (z=-2.1)")
- Link → `/retention/{user_id}/detail`

### Card 2: Scorecard Top/Bottom 3
**Source**: `performance.compute_performance(db, current_quarter)`
**Data**: `results[:3]` (top) + `results[-3:]` (bottom)
**Display per item**:
- Rank + medal (🥇🥈🥉 for top 3)
- Member name
- Overall score (sum of ranks)
- Link → `/users/{user_id}`

### Card 3: SLA Breach
**Source**: `WorkItem` query
**Criteria**: `status IN ('Open','Blocked')` AND `created_at < now - 30 days`
**Display**:
- Summary: breach count, breach rate%, total active
- Top 5 oldest items: title, assignee, days open, service badge
- Link all → `/dashboard/triage`

### Card 4: Stale Critical Services
**Source**: Combine `leader_alerts.check_stale_items()` + `check_critical_service_load()`
**Filter**: Items from critical services only (Kubernetes, Cloudflare, Backup)
**Display**:
- Top 5 oldest: title, assignee, days open, service badge (red)
- Link all → `/dashboard/triage`

---

## Data Flow
```
GET /dashboard/executive
    │
    ├─► db.query(RetentionScore) for current month
    ├─► performance.compute_performance(db, current_quarter)
    ├─► WorkItem query (SLA: open >30d)
    └─► WorkItem query (stale + critical services)
    │
    ▼
TemplateResponse("dashboard_executive.html", {retention_cards, scorecard_cards, sla_items, stale_items})
```

---

## Template: `dashboard_executive.html`
- Extends `base.html`
- Bootstrap 5 grid: `<div class="row g-3">` + 4x `col-md-3`
- Each card: `.card.h-100` with header, body (list), footer (view all link)
- Color coding: Retention (danger/warning), Scorecard (warning for medals), SLA (danger), Stale (dark)

---

## Navbar Integration
In `base.html` dropdown "Dashboards":
```html
<a class="dropdown-item" href="/dashboard/executive">📊 Executive Summary</a>
```
Positioned at top of dropdown.

---

## Acceptance Criteria
1. Page loads in <500ms on local SQLite
2. All 4 cards render with correct data
3. Click retention member → `/retention/{id}/detail`
4. Click scorecard member → `/users/{id}`
5. Click SLA/stale "View all" → `/dashboard/triage`
6. Mobile responsive (cards stack vertically)
7. Empty states handled gracefully (no data → "No high-risk members" etc.)

---

## Out of Scope
- Real-time updates / WebSocket
- Caching layer
- HTMX partial loads
- New models or migrations
- Export CSV (can add later)