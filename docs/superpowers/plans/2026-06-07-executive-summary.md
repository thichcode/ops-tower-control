# Executive Summary Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build single-page Executive Summary at `/dashboard/executive` combining retention high-risk + scorecard extremes + SLA breaches + stale critical items into 4-card grid.

**Architecture:** New route in existing `app/routers/dashboards.py` aggregates 4 existing services (retention, performance, KPI, leader_alerts). New Jinja2 template renders 4 cards. Navbar link added. No new models.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2, Bootstrap 5

---

## File Structure
- **Modify:** `app/routers/dashboards.py` — add `/executive` route
- **Create:** `app/templates/dashboard_executive.html` — 4-card grid template
- **Modify:** `app/templates/base.html` — add Executive Summary link to Dashboards dropdown
- **Modify:** `README.md` — add screenshot to features section

---

### Task 1: Add Executive Summary Route

**Files:**
- Modify: `app/routers/dashboards.py` (add at end, after `kpi` route)

- [ ] **Step 1: Add the route function**

Append to `app/routers/dashboards.py` (after the `kpi_metrics` function, line 497):

```python
@router.get("/executive")
def executive_summary(request: Request, db: Session = Depends(get_db)):
    from datetime import datetime, timezone
    from app.models import RetentionScore
    from app.services.performance import compute_performance, Period, get_available_periods

    now = datetime.now(timezone.utc)
    current_month = now.strftime("%Y-%m")
    current_year = now.year
    current_quarter = (now.month - 1) // 3 + 1

    # Card 1: Retention high-risk (top 5 non-Low)
    retention_cards = db.query(RetentionScore).filter(
        RetentionScore.month == current_month,
        RetentionScore.risk_level != "Low",
    ).order_by(
        RetentionScore.flag_count.desc(),
    ).limit(5).all()

    retention_data = []
    for r in retention_cards:
        user = db.query(User).filter(User.id == r.user_id).first()
        signals = r.signals or {}
        flagged = []
        if signals.get("leave_z", 0) > 2:
            flagged.append(f"Leave {signals.get('leave_current', 0):.0f}h (z={signals.get('leave_z')})")
        if signals.get("throughput_z", 0) < -2:
            flagged.append(f"Throughput {signals.get('throughput_current')}/wk (z={signals.get('throughput_z')})")
        if signals.get("cycle_time_z", 0) > 2:
            flagged.append(f"Cycle {signals.get('cycle_time_current', 0):.1f}d (z={signals.get('cycle_time_z')})")
        if signals.get("utilization_pct", 0) > 100 or signals.get("utilization_pct", 0) < 30:
            flagged.append(f"Util {signals.get('utilization_pct', 0):.0f}%")
        if signals.get("meeting_z", 0) > 2:
            flagged.append(f"Meetings {signals.get('meeting_current', 0):.0f}h (z={signals.get('meeting_z')})")
        if signals.get("blocked_ratio_z", 0) > 2:
            flagged.append(f"Blocked {signals.get('blocked_ratio_current', 0)*100:.0f}%")
        retention_data.append({
            "user": user,
            "risk_level": r.risk_level,
            "flag_count": r.flag_count,
            "flagged_signals": flagged[:2],
        })

    # Card 2: Scorecard top/bottom 3
    period = Period("quarter", current_year, current_quarter)
    perf_results = compute_performance(db, period)
    scorecard_top = perf_results[:3] if len(perf_results) >= 3 else perf_results
    scorecard_bottom = perf_results[-3:] if len(perf_results) >= 3 else []

    # Card 3: SLA Breach (open > 30 days)
    from datetime import timedelta
    sla_threshold = now - timedelta(days=30)
    sla_items_query = db.query(WorkItem).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.created_at < sla_threshold,
    ).order_by(WorkItem.created_at.asc()).limit(5).all()

    total_active = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
    ).scalar() or 0
    sla_count = db.query(func.count(WorkItem.id)).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.created_at < sla_threshold,
    ).scalar() or 0
    sla_rate = round(int(sla_count) / int(total_active) * 100, 1) if total_active > 0 else 0

    sla_items = []
    for item in sla_items_query:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        sla_items.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee.display_name if item.assignee else "Unassigned",
            "days_open": (now - created).days,
            "service": item.service.name if item.service else "-",
        })

    # Card 4: Stale Critical (oldest in Kubernetes/Cloudflare/Backup)
    critical_names = {"Kubernetes", "Cloudflare", "Backup"}
    critical_services = db.query(Service).filter(Service.name.in_(critical_names)).all()
    critical_ids = [s.id for s in critical_services]

    stale_items_query = db.query(WorkItem).filter(
        WorkItem.status.in_(["Open", "Blocked"]),
        WorkItem.service_id.in_(critical_ids),
    ).order_by(WorkItem.created_at.asc()).limit(5).all()

    stale_items = []
    for item in stale_items_query:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        stale_items.append({
            "id": item.id,
            "title": item.title,
            "assignee": item.assignee.display_name if item.assignee else "Unassigned",
            "days_open": (now - created).days,
            "service": item.service.name if item.service else "-",
        })

    return TemplateResponse("dashboard_executive.html", {
        "request": request,
        "retention_data": retention_data,
        "scorecard_top": scorecard_top,
        "scorecard_bottom": scorecard_bottom,
        "sla_items": sla_items,
        "sla_count": int(sla_count),
        "sla_rate": sla_rate,
        "total_active": int(total_active),
        "stale_items": stale_items,
        "current_month": current_month,
    })
```

- [ ] **Step 2: Test the route loads**

Run server on test port:
```bash
cd D:\pupeteer\opsdash
python -m uvicorn app.main:app --port 6401 &
sleep 5
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:6401/dashboard/executive
```

Expected: `200`

Stop the server:
```bash
# Find PID on port 6401 and kill (Windows)
Get-NetTCPConnection -LocalPort 6401 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

- [ ] **Step 3: Commit**

```bash
cd D:\pupeteer\opsdash
git add app/routers/dashboards.py
git commit -m "feat: add /dashboard/executive route"
```

---

### Task 2: Create Executive Summary Template

**Files:**
- Create: `app/templates/dashboard_executive.html`

- [ ] **Step 1: Create the template file**

```html
{% extends "base.html" %}
{% block title %}Executive Summary{% endblock %}
{% block content %}

<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>📊 Executive Summary</h2>
  <span class="text-muted">{{ current_month }} · 1-click situational view</span>
</div>

<div class="row g-3">

  <!-- Card 1: Retention High Risk -->
  <div class="col-md-3">
    <div class="card border-danger h-100">
      <div class="card-header bg-danger text-white d-flex justify-content-between">
        <strong>🧠 Retention Risk</strong>
        <span class="badge bg-light text-dark">{{ retention_data|length }}</span>
      </div>
      <div class="card-body p-0">
        {% if retention_data %}
          <ul class="list-group list-group-flush">
            {% for r in retention_data %}
            {% set badge = 'danger' if r.risk_level == 'High' else 'warning' %}
            <li class="list-group-item small">
              <div class="d-flex justify-content-between align-items-start">
                <a href="/retention/{{ r.user.id }}/detail" class="text-decoration-none fw-bold">{{ r.user.display_name }}</a>
                <span class="badge bg-{{ badge }}">{{ r.risk_level }}</span>
              </div>
              {% for sig in r.flagged_signals %}
              <div class="text-muted">• {{ sig }}</div>
              {% endfor %}
            </li>
            {% endfor %}
          </ul>
        {% else %}
          <div class="p-3 text-center text-muted small">✅ No high-risk members</div>
        {% endif %}
      </div>
      <div class="card-footer text-center">
        <a href="/retention" class="btn btn-outline-danger btn-sm">View All →</a>
      </div>
    </div>
  </div>

  <!-- Card 2: Scorecard Top/Bottom 3 -->
  <div class="col-md-3">
    <div class="card border-warning h-100">
      <div class="card-header bg-warning text-dark">
        <strong>🏆 Scorecard</strong>
      </div>
      <div class="card-body p-0">
        {% if scorecard_top %}
        <div class="px-3 py-2 bg-light small fw-bold">⬆ Top 3</div>
        <ul class="list-group list-group-flush">
          {% for r in scorecard_top %}
          {% set medal = '🥇' if r.overall_rank == 1 else '🥈' if r.overall_rank == 2 else '🥉' %}
          <li class="list-group-item small">
            <a href="/users/{{ r.user.id }}" class="text-decoration-none fw-bold">{{ medal }} {{ r.user.display_name }}</a>
            <span class="float-end text-muted">#{{ r.overall_rank }} ({{ r.overall_score }})</span>
          </li>
          {% endfor %}
        </ul>
        {% if scorecard_bottom and scorecard_bottom|length > 0 and scorecard_bottom[0].user.id != scorecard_top[-1].user.id %}
        <div class="px-3 py-2 bg-light small fw-bold border-top">⬇ Bottom 3</div>
        <ul class="list-group list-group-flush">
          {% for r in scorecard_bottom %}
          <li class="list-group-item small">
            <a href="/users/{{ r.user.id }}" class="text-decoration-none">{{ r.user.display_name }}</a>
            <span class="float-end text-muted">#{{ r.overall_rank }} ({{ r.overall_score }})</span>
          </li>
          {% endfor %}
        </ul>
        {% endif %}
        {% else %}
          <div class="p-3 text-center text-muted small">No scorecard data</div>
        {% endif %}
      </div>
      <div class="card-footer text-center">
        <a href="/performance" class="btn btn-outline-warning btn-sm">View All →</a>
      </div>
    </div>
  </div>

  <!-- Card 3: SLA Breach -->
  <div class="col-md-3">
    <div class="card border-warning h-100">
      <div class="card-header bg-warning text-dark d-flex justify-content-between">
        <strong>⚠️ SLA Breach</strong>
        <span class="badge bg-dark">{{ sla_count }} ({{ sla_rate }}%)</span>
      </div>
      <div class="card-body p-0">
        {% if sla_items %}
          <ul class="list-group list-group-flush">
            {% for i in sla_items %}
            <li class="list-group-item small">
              <a href="/dashboard/triage" class="text-decoration-none">#{{ i.id }} {{ i.title[:35] }}{% if i.title|length > 35 %}…{% endif %}</a>
              <div class="text-muted">👤 {{ i.assignee }} · {{ i.days_open }}d · {{ i.service }}</div>
            </li>
            {% endfor %}
          </ul>
        {% else %}
          <div class="p-3 text-center text-muted small">✅ No SLA breaches</div>
        {% endif %}
      </div>
      <div class="card-footer text-center">
        <a href="/dashboard/triage" class="btn btn-outline-warning btn-sm">View Triage →</a>
      </div>
    </div>
  </div>

  <!-- Card 4: Stale Critical -->
  <div class="col-md-3">
    <div class="card border-dark h-100">
      <div class="card-header bg-dark text-white d-flex justify-content-between">
        <strong>🔴 Stale Critical</strong>
        <span class="badge bg-light text-dark">{{ stale_items|length }}</span>
      </div>
      <div class="card-body p-0">
        {% if stale_items %}
          <ul class="list-group list-group-flush">
            {% for i in stale_items %}
            <li class="list-group-item small">
              <a href="/dashboard/triage" class="text-decoration-none">#{{ i.id }} {{ i.title[:35] }}{% if i.title|length > 35 %}…{% endif %}</a>
              <div class="text-muted">👤 {{ i.assignee }} · <span class="text-danger fw-bold">{{ i.days_open }}d</span> · {{ i.service }}</div>
            </li>
            {% endfor %}
          </ul>
        {% else %}
          <div class="p-3 text-center text-muted small">✅ No stale critical items</div>
        {% endif %}
      </div>
      <div class="card-footer text-center">
        <a href="/dashboard/triage" class="btn btn-outline-dark btn-sm">View Triage →</a>
      </div>
    </div>
  </div>

</div>

{% endblock %}
```

- [ ] **Step 2: Verify template renders without error**

```bash
cd D:\pupeteer\opsdash
python -m uvicorn app.main:app --port 6401 &
sleep 5
curl -s http://localhost:6401/dashboard/executive | head -20
```

Expected: HTML output with "Executive Summary" title and 4 card headers.

Stop server:
```bash
Get-NetTcpConnection -LocalPort 6401 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

- [ ] **Step 3: Commit**

```bash
cd D:\pupeteer\opsdash
git add app/templates/dashboard_executive.html
git commit -m "feat: add executive summary template with 4-card grid"
```

---

### Task 3: Add Navbar Link

**Files:**
- Modify: `app/templates/base.html` (Dashboards dropdown)

- [ ] **Step 1: Find the Dashboards dropdown**

Search for the Dashboards dropdown in `app/templates/base.html`. Look for the first dropdown-item with `/dashboard/` link.

- [ ] **Step 2: Add Executive Summary as first item**

Insert at the top of the Dashboards dropdown items:

```html
<a class="dropdown-item" href="/dashboard/executive">📊 Executive Summary</a>
<div class="dropdown-divider"></div>
```

(Add a divider after Executive Summary to separate it from the detailed dashboards below)

- [ ] **Step 3: Verify navbar renders**

```bash
cd D:\pupeteer\opsdash
python -m uvicorn app.main:app --port 6401 &
sleep 5
curl -s http://localhost:6401/ | grep -i "executive"
```

Expected: line containing "Executive Summary" link

Stop server:
```bash
Get-NetTcpConnection -LocalPort 6401 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

- [ ] **Step 4: Commit**

```bash
cd D:\pupeteer\opsdash
git add app/templates/base.html
git commit -m "feat: add executive summary link to dashboard navbar"
```

---

### Task 4: Test All Links Work

**Files:**
- Test: Manual verification of all clickable links

- [ ] **Step 1: Start server and test all 4 card types**

```bash
cd D:\pupeteer\opsdash
python -m uvicorn app.main:app --port 6401 &
sleep 5
```

Test each card's "View All" / member links:
```bash
# Executive summary loads
curl -s -o /dev/null -w "Executive: %{http_code}\n" http://localhost:6401/dashboard/executive

# Retention detail (if any high-risk members exist)
curl -s -o /dev/null -w "Retention: %{http_code}\n" http://localhost:6401/retention

# Scorecard
curl -s -o /dev/null -w "Performance: %{http_code}\n" http://localhost:6401/performance

# Triage
curl -s -o /dev/null -w "Triage: %{http_code}\n" http://localhost:6401/dashboard/triage

# User detail
curl -s -o /dev/null -w "User: %{http_code}\n" http://localhost:6401/users/1
```

Expected: All return `200`

Stop server:
```bash
Get-NetTcpConnection -LocalPort 6401 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

- [ ] **Step 2: Commit verification log (if needed)**

No commit needed unless test failures require fixes.

---

### Task 5: Take Screenshot & Update README

**Files:**
- Create: `screenshots/executive.png`
- Modify: `README.md`

- [ ] **Step 1: Start server for screenshot**

```bash
cd D:\pupeteer\opsdash
python -m uvicorn app.main:app --port 6401 &
sleep 5
```

- [ ] **Step 2: Take screenshot using Playwright/headless browser**

Open browser to `http://localhost:6401/dashboard/executive`, full page, save to `screenshots/executive.png`.

If using Chrome headless:
```bash
# Using puppeteer/playwright if available, or manual
```

If no automated tool available, use a different approach: manually capture via browser or document that user should take screenshot.

- [ ] **Step 3: Add screenshot to README**

In `README.md` features section, add:

```markdown
### 📊 Executive Summary
One-glance situational view combining retention risks, scorecard extremes, SLA breaches, and stale critical items.
![Executive Summary](screenshots/executive.png)
```

Place near top of features list, after overview.

- [ ] **Step 4: Commit**

```bash
cd D:\pupeteer\opsdash
git add screenshots/executive.png README.md
git commit -m "docs: add executive summary screenshot to README"
```

Stop server if still running:
```bash
Get-NetTcpConnection -LocalPort 6401 | Select-Object -ExpandProperty OwningProcess | ForEach-Object { Stop-Process -Id $_ -Force }
```

---

### Task 6: Push to GitHub

- [ ] **Step 1: Push all commits**

```bash
cd D:\pupeteer\opsdash
git push
```

Expected: All commits pushed to main, GitHub Action will auto-create a release.
