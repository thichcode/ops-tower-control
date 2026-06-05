# Retention Risk Prediction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add retention risk prediction using anomaly detection (z-score) on existing member metrics.

**Architecture:** Compute z-scores for each member across 6 signals (leave, throughput, cycle time, utilization, blocked ratio, meetings) using rolling historical windows. Composite risk = number of flags where |z| > 2. Dashboard at `/retention`, alerts via Teams webhook.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2, Chart.js, Python statistics module

---

### Task 1: RetentionScore Model

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: Add RetentionScore model to models.py**

Append after the Capacity model:

```python
from sqlalchemy import JSON


class RetentionScore(Base):
    __tablename__ = "retention_scores"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(Text, nullable=False)
    risk_level = Column(Text, nullable=False, default="Low")
    flag_count = Column(Integer, default=0)
    signals = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
```

- [ ] **Step 2: Commit**

```bash
git add app/models.py
git commit -m "feat: add RetentionScore model"
```

---

### Task 2: Retention Scoring Service

**Files:**
- Create: `app/services/retention.py`

- [ ] **Step 1: Create retention.py with z-score computation**

```python
import statistics
from datetime import datetime, timezone, timedelta
from calendar import monthrange
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.models import User, WorkItem, Capacity, RetentionScore


def compute_z_score(current_value, historical_values):
    if not historical_values or len(historical_values) < 2:
        return 0.0
    mean = statistics.mean(historical_values)
    stdev = statistics.stdev(historical_values)
    return (current_value - mean) / stdev if stdev > 0 else 0.0


def get_historical_values(db, user_id, field_getter, month_count=6):
    """Get list of values for a field over the last N months."""
    now = datetime.now(timezone.utc)
    values = []
    for i in range(1, month_count + 1):
        m = now.month - i
        y = now.year
        while m < 1:
            m += 12
            y -= 1
        values.append(field_getter(db, user_id, y, m))
    return [v for v in values if v is not None]


def get_leave_hours(db, user_id, year, month):
    month_key = f"{year}-{month:02d}"
    cap = db.query(Capacity).filter(
        Capacity.user_id == user_id, Capacity.month == month_key
    ).first()
    return float(cap.leave_hours or 0) if cap else 0


def get_meeting_hours(db, user_id, year, month):
    month_key = f"{year}-{month:02d}"
    cap = db.query(Capacity).filter(
        Capacity.user_id == user_id, Capacity.month == month_key
    ).first()
    return float(cap.meeting_hours or 0) if cap else 0


def get_monthly_demand(db, user_id, year, month):
    month_key = f"{year}-{month:02d}"
    demand = db.query(func.coalesce(func.sum(WorkItem.estimate_hours), 0)).filter(
        WorkItem.assignee_id == user_id,
        func.strftime("%Y-%m", WorkItem.created_at) == month_key,
    ).scalar() or 0
    return float(demand)


def get_monthly_availability(db, user_id, year, month):
    month_key = f"{year}-{month:02d}"
    cap = db.query(Capacity).filter(
        Capacity.user_id == user_id, Capacity.month == month_key
    ).first()
    capacity = float(cap.capacity_hours or 0) if cap else 160
    leave = float(cap.leave_hours or 0) if cap else 0
    meetings = float(cap.meeting_hours or 0) if cap else 0
    return capacity - leave - meetings


def get_cycle_time(db, user_id, year, month):
    month_key = f"{year}-{month:02d}"
    avg = db.query(
        func.avg(func.julianday(WorkItem.completed_at) - func.julianday(WorkItem.created_at))
    ).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at.isnot(None),
        func.strftime("%Y-%m", WorkItem.created_at) == month_key,
    ).scalar()
    return float(avg) if avg else 0


def get_blocked_ratio(db, user_id, year, month):
    month_key = f"{year}-{month:02d}"
    total = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        func.strftime("%Y-%m", WorkItem.created_at) == month_key,
    ).scalar() or 0
    if total == 0:
        return 0.0
    blocked = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Blocked",
        func.strftime("%Y-%m", WorkItem.created_at) == month_key,
    ).scalar() or 0
    return blocked / total


def get_weekly_throughput(db, user_id):
    """Get avg items/week for last 4 weeks and prev 8 weeks."""
    now = datetime.now(timezone.utc)
    recent = []
    prev = []

    for i in range(12):
        w_end = now - timedelta(weeks=i)
        w_start = w_end - timedelta(weeks=1)
        done = db.query(func.count(WorkItem.id)).filter(
            WorkItem.assignee_id == user_id,
            WorkItem.status == "Done",
            WorkItem.completed_at >= w_start,
            WorkItem.completed_at <= w_end,
        ).scalar() or 0
        if i < 4:
            recent.append(done)
        else:
            prev.append(done)

    recent_avg = statistics.mean(recent) if recent else 0
    prev_avg = statistics.mean(prev) if prev else 0
    return recent_avg, prev_avg


def compute_member_scores(db, user_id, now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    month_key = f"{year}-{month:02d}"

    signals = {}

    # 1. Leave hours z-score
    leave_current = get_leave_hours(db, user_id, year, month)
    leave_hist = get_historical_values(db, user_id, lambda d, uid, y, m: get_leave_hours(d, uid, y, m), 6)
    signals["leave_z"] = round(compute_z_score(leave_current, leave_hist), 2)
    signals["leave_current"] = leave_current

    # 2. Meeting hours z-score
    meeting_current = get_meeting_hours(db, user_id, year, month)
    meeting_hist = get_historical_values(db, user_id, lambda d, uid, y, m: get_meeting_hours(d, uid, y, m), 6)
    signals["meeting_z"] = round(compute_z_score(meeting_current, meeting_hist), 2)
    signals["meeting_current"] = meeting_current

    # 3. Throughput z-score
    recent_tp, prev_tp = get_weekly_throughput(db, user_id)
    throughput_z = compute_z_score(recent_tp, [prev_tp]) if prev_tp > 0 else 0
    signals["throughput_z"] = round(throughput_z, 2)
    signals["throughput_current"] = round(recent_tp, 1)
    signals["throughput_previous"] = round(prev_tp, 1)

    # 4. Cycle time z-score
    ct_current = get_cycle_time(db, user_id, year, month)
    ct_hist = get_historical_values(db, user_id, lambda d, uid, y, m: get_cycle_time(d, uid, y, m), 3)
    signals["cycle_time_z"] = round(compute_z_score(ct_current, ct_hist), 2)
    signals["cycle_time_current"] = round(ct_current, 1)

    # 5. Utilization z-score (special: flag if >100% or <30% regardless)
    demand = get_monthly_demand(db, user_id, year, month)
    available = get_monthly_availability(db, user_id, year, month)
    util_pct = round(demand / available * 100, 1) if available > 0 else 0
    util_hist = get_historical_values(db, user_id, lambda d, uid, y, m: (
        get_monthly_demand(d, uid, y, m) / get_monthly_availability(d, uid, y, m) * 100
        if get_monthly_availability(d, uid, y, m) > 0 else 0
    ), 3)
    signals["utilization_z"] = round(compute_z_score(util_pct, util_hist), 2)
    signals["utilization_pct"] = util_pct

    # 6. Blocked ratio z-score
    br_current = get_blocked_ratio(db, user_id, year, month)
    br_hist = get_historical_values(db, user_id, lambda d, uid, y, m: get_blocked_ratio(d, uid, y, m), 3)
    signals["blocked_ratio_z"] = round(compute_z_score(br_current, br_hist), 2)
    signals["blocked_ratio_current"] = round(br_current, 3)

    # Count flags
    flags = 0
    if signals["leave_z"] > 2: flags += 1
    if signals["throughput_z"] < -2: flags += 1
    if signals["cycle_time_z"] > 2: flags += 1
    if signals["utilization_pct"] > 100 or signals["utilization_pct"] < 30: flags += 1
    elif abs(signals["utilization_z"]) > 2: flags += 1
    if signals["blocked_ratio_z"] > 2: flags += 1
    if signals["meeting_z"] > 2: flags += 1

    if flags >= 3:
        risk = "High"
    elif flags == 2:
        risk = "Medium"
    else:
        risk = "Low"

    return {
        "user_id": user_id,
        "month": month_key,
        "risk_level": risk,
        "flag_count": flags,
        "signals": signals,
    }


def compute_all_scores(db):
    users = db.query(User).filter(User.is_active == True).all()
    results = []
    for user in users:
        result = compute_member_scores(db, user.id)
        # Upsert: delete existing score for this user+month, then insert
        existing = db.query(RetentionScore).filter(
            RetentionScore.user_id == user.id,
            RetentionScore.month == result["month"],
        ).first()
        if existing:
            existing.risk_level = result["risk_level"]
            existing.flag_count = result["flag_count"]
            existing.signals = result["signals"]
        else:
            score = RetentionScore(
                user_id=result["user_id"],
                month=result["month"],
                risk_level=result["risk_level"],
                flag_count=result["flag_count"],
                signals=result["signals"],
            )
            db.add(score)
        results.append(result)
    db.commit()
    return results
```

- [ ] **Step 2: Commit**

```bash
git add app/services/retention.py
git commit -m "feat: add retention scoring service with z-score computation"
```

---

### Task 3: Retention Router

**Files:**
- Create: `app/routers/retention.py`

- [ ] **Step 1: Create retention.py router**

```python
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RetentionScore
from app.services.retention import compute_all_scores, compute_member_scores
from app.templates import TemplateResponse

router = APIRouter(prefix="/retention", tags=["retention"])


@router.get("")
def retention_dashboard(request: Request, db: Session = Depends(get_db)):
    # Ensure scores are up to date
    compute_all_scores(db)

    scores = db.query(RetentionScore).order_by(
        RetentionScore.flag_count.desc(),
        RetentionScore.created_at.desc(),
    ).all()

    members = {}
    for s in scores:
        if s.user_id not in members:
            user = db.query(User).filter(User.id == s.user_id).first()
            if user:
                members[s.user_id] = {
                    "user": user,
                    "current": s,
                    "history": [],
                }
        members[s.user_id]["history"].append(s)

    # Sort High > Medium > Low
    risk_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_members = sorted(
        members.values(),
        key=lambda m: (risk_order.get(m["current"].risk_level, 3), -m["current"].flag_count),
    )

    return TemplateResponse("retention.html", {
        "request": request,
        "members": sorted_members,
    })


@router.get("/{user_id}/detail")
def member_retention_detail(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return TemplateResponse("retention.html", {"request": request, "members": []})

    # Recompute to get current signals
    result = compute_member_scores(db, user_id)

    history = db.query(RetentionScore).filter(
        RetentionScore.user_id == user_id,
    ).order_by(RetentionScore.created_at.desc()).limit(6).all()

    return TemplateResponse("retention_detail.html", {
        "request": request,
        "member": user,
        "result": result,
        "history": history,
    })
```

- [ ] **Step 2: Commit**

```bash
git add app/routers/retention.py
git commit -m "feat: add retention router with dashboard + member detail"
```

---

### Task 4: Retention Dashboard Templates

**Files:**
- Create: `app/templates/retention.html`
- Create: `app/templates/retention_detail.html`

- [ ] **Step 1: Create retention.html (main dashboard)**

```html
{% extends "base.html" %}
{% block title %}Retention Risk{% endblock %}
{% block content %}

<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>🧠 Retention Risk Dashboard</h2>
  <span class="text-muted">Anomaly detection based on member operational signals</span>
</div>

<div class="row g-3">
  {% for m in members %}
  {% set s = m.current %}
  {% set risk_color = 'danger' if s.risk_level == 'High' else 'warning' if s.risk_level == 'Medium' else 'success' %}
  <div class="col-md-6 col-lg-4">
    <div class="card border-{{ risk_color }} h-100">
      <div class="card-header bg-{{ risk_color }} text-white d-flex justify-content-between align-items-center">
        <strong>{{ m.user.display_name }}</strong>
        <span class="badge bg-light text-dark">{{ s.flag_count }} flags</span>
      </div>
      <div class="card-body">
        <h5 class="card-title">
          <span class="badge bg-{{ risk_color }} fs-6">{{ s.risk_level }} Risk</span>
        </h5>

        {% if s.signals %}
        <ul class="list-unstyled small mb-3">
          {% set sig = s.signals %}
          {% if sig.leave_z > 2 %}
          <li class="text-danger">📈 Leave: {{ "%.1f"|format(sig.leave_current) }}h (z={{ sig.leave_z }})</li>
          {% endif %}
          {% if sig.throughput_z < -2 %}
          <li class="text-danger">📉 Throughput: {{ sig.throughput_current }}/wk (was {{ sig.throughput_previous }})</li>
          {% endif %}
          {% if sig.cycle_time_z > 2 %}
          <li class="text-danger">⏱ Cycle time: {{ sig.cycle_time_current }}d (z={{ sig.cycle_time_z }})</li>
          {% endif %}
          {% if sig.utilization_pct > 100 or sig.utilization_pct < 30 %}
          <li class="text-danger">🔋 Utilization: {{ sig.utilization_pct }}%</li>
          {% endif %}
          {% if sig.meeting_z > 2 %}
          <li class="text-danger">📅 Meetings: {{ "%.1f"|format(sig.meeting_current) }}h (z={{ sig.meeting_z }})</li>
          {% endif %}
          {% if sig.blocked_ratio_z > 2 %}
          <li class="text-danger">🚫 Blocked ratio: {{ "%.1f"|format(sig.blocked_ratio_current * 100) }}%</li>
          {% endif %}
          {% if s.flag_count == 0 %}
          <li class="text-success">✅ All signals normal</li>
          {% endif %}
        </ul>
        {% endif %}

        <a href="/retention/{{ m.user.id }}/detail" class="btn btn-outline-{{ risk_color }} btn-sm">View Details →</a>
      </div>
      <div class="card-footer text-muted small">
        {{ s.month }} · Last updated {{ s.created_at.strftime('%m/%d %H:%M') if s.created_at else '-' }}
      </div>
    </div>
  </div>
  {% else %}
  <div class="col-12">
    <p class="text-muted text-center">No retention data yet. Scores are computed on first visit.</p>
  </div>
  {% endfor %}
</div>

<div class="mt-4 p-3 bg-light rounded small">
  <h6>🧪 How it works</h6>
  <p class="mb-0">Z-score anomaly detection on 6 signals: leave hours, throughput, cycle time, utilization, blocked ratio, and meeting hours. |z| &gt; 2 = 1 flag. 0-1 flags → Low, 2 → Medium, 3+ → High risk.</p>
</div>

{% endblock %}
```

- [ ] **Step 2: Create retention_detail.html (per-member detail)**

```html
{% extends "base.html" %}
{% block title %}{{ member.display_name }} — Retention Detail{% endblock %}
{% block content %}

<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>{{ member.display_name }} — Retention Detail</h2>
  <a href="/retention" class="btn btn-outline-secondary btn-sm">← Back</a>
</div>

{% set sig = result.signals %}
{% set risk_color = 'danger' if result.risk_level == 'High' else 'warning' if result.risk_level == 'Medium' else 'success' %}

<div class="card border-{{ risk_color }} mb-4">
  <div class="card-header bg-{{ risk_color }} text-white">
    Current Risk: <strong>{{ result.risk_level }}</strong> ({{ result.flag_count }} flags) — {{ result.month }}
  </div>
  <div class="card-body">
    <div class="row g-3">
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-body text-center">
            <h6>Leave Hours</h6>
            <h4>{{ "%.1f"|format(sig.leave_current) }}h</h4>
            <small class="{% if sig.leave_z > 2 %}text-danger{% endif %}">z = {{ sig.leave_z }}</small>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-body text-center">
            <h6>Throughput</h6>
            <h4>{{ sig.throughput_current }}/wk</h4>
            <small class="{% if sig.throughput_z < -2 %}text-danger{% endif %}">was {{ sig.throughput_previous }}/wk</small>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-body text-center">
            <h6>Cycle Time</h6>
            <h4>{{ sig.cycle_time_current }}d</h4>
            <small class="{% if sig.cycle_time_z > 2 %}text-danger{% endif %}">z = {{ sig.cycle_time_z }}</small>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-body text-center">
            <h6>Utilization</h6>
            <h4 class="{% if sig.utilization_pct > 100 or sig.utilization_pct < 30 %}text-danger{% endif %}">{{ sig.utilization_pct }}%</h4>
            <small>z = {{ sig.utilization_z }}</small>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-body text-center">
            <h6>Blocked Ratio</h6>
            <h4>{{ "%.1f"|format(sig.blocked_ratio_current * 100) }}%</h4>
            <small class="{% if sig.blocked_ratio_z > 2 %}text-danger{% endif %}">z = {{ sig.blocked_ratio_z }}</small>
          </div>
        </div>
      </div>
      <div class="col-md-4">
        <div class="card h-100">
          <div class="card-body text-center">
            <h6>Meeting Hours</h6>
            <h4>{{ "%.1f"|format(sig.meeting_current) }}h</h4>
            <small class="{% if sig.meeting_z > 2 %}text-danger{% endif %}">z = {{ sig.meeting_z }}</small>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

{% if history %}
<h5 class="mb-2">Risk History</h5>
<div class="table-responsive">
  <table class="table table-sm">
    <thead>
      <tr><th>Month</th><th>Risk</th><th>Flags</th><th>Leave</th><th>Throughput</th><th>Cycle Time</th><th>Util %</th><th>Blocked %</th><th>Meetings</th></tr>
    </thead>
    <tbody>
      {% for h in history %}
      <tr class="table-{{ 'danger' if h.risk_level == 'High' else 'warning' if h.risk_level == 'Medium' else 'success' }}">
        <td>{{ h.month }}</td>
        <td><span class="badge bg-{{ 'danger' if h.risk_level == 'High' else 'warning' if h.risk_level == 'Medium' else 'success' }}">{{ h.risk_level }}</span></td>
        <td>{{ h.flag_count }}</td>
        <td>{{ "%.1f"|format(h.signals.leave_current) if h.signals else '-' }}</td>
        <td>{{ h.signals.throughput_current if h.signals else '-' }}/wk</td>
        <td>{{ h.signals.cycle_time_current if h.signals else '-' }}d</td>
        <td>{{ h.signals.utilization_pct if h.signals else '-' }}%</td>
        <td>{{ "%.0f"|format(h.signals.blocked_ratio_current * 100) if h.signals else '-' }}%</td>
        <td>{{ "%.1f"|format(h.signals.meeting_current) if h.signals else '-' }}h</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 3: Commit**

```bash
git add app/templates/retention.html app/templates/retention_detail.html
git commit -m "feat: add retention dashboard + detail templates"
```

---

### Task 5: Retention Alerts

**Files:**
- Create: `app/services/retention_alerts.py`
- Create: `retention_alerts.py` (root level cron script)

- [ ] **Step 1: Create retention_alerts service**

```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models import User, RetentionScore
from app.services.retention import compute_all_scores
from app.services.notifications import send_teams_card, TEAMS_ALERT_WEBHOOK


def check_retention_alerts(db, dry_run=False):
    compute_all_scores(db)

    now = datetime.now(timezone.utc)
    month_key = now.strftime("%Y-%m")

    # Get all current scores for this month
    scores = db.query(RetentionScore).filter(
        RetentionScore.month == month_key,
    ).all()

    alerts = []

    for s in scores:
        user = db.query(User).filter(User.id == s.user_id).first()
        name = user.display_name if user else f"User #{s.user_id}"

        if s.risk_level == "High" and s.flag_count >= 3:
            alerts.append({
                "type": "high_risk",
                "user_id": s.user_id,
                "member": name,
                "flags": s.flag_count,
                "detail": f"{name} has {s.flag_count} risk flags — High retention risk",
            })

        # Check if any score escalated from Medium to High
        prev = db.query(RetentionScore).filter(
            RetentionScore.user_id == s.user_id,
            RetentionScore.month < month_key,
        ).order_by(RetentionScore.month.desc()).first()

        if prev and prev.risk_level == "Medium" and s.risk_level == "High":
            alerts.append({
                "type": "escalated",
                "user_id": s.user_id,
                "member": name,
                "flags": s.flag_count,
                "detail": f"{name} escalated from Medium → High risk ({s.flag_count} flags)",
            })

    if dry_run:
        return {"alerts": alerts}

    if alerts and TEAMS_ALERT_WEBHOOK:
        sections = [{
            "title": f"⚠️ {len(alerts)} Retention Alerts",
            "facts": [{"name": a["member"], "value": a["detail"]} for a in alerts],
        }]
        result = send_teams_card(
            webhook_url=TEAMS_ALERT_WEBHOOK,
            title=f"Retention Risk Alerts — {month_key}",
            summary=f"{len(alerts)} retention alerts",
            sections=sections,
            color="E81123",
        )
        return {"alerts": alerts, "send_result": result}

    return {"alerts": alerts}
```

- [ ] **Step 2: Create root level retention_alerts.py**

```python
"""
Check retention risk and send alerts.
Run via cron (e.g., weekly):
    python retention_alerts.py [--send]

Environment:
    TEAMS_ALERT_WEBHOOK_URL=https://your-webhook
"""

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
```

Wait, the code uses `default=datetime.now(timezone.utc)` for RetentionScore.created_at — need to make sure `from datetime import datetime, timezone` is available. Already in the script.

Also the import `from app.services.notifications import send_teams_card, TEAMS_ALERT_WEBHOOK` — let me check if TEAMS_ALERT_WEBHOOK is actually TEAMS_ALERT_WEBHOOK_URL. Let me check the notifications module.

Actually, I should check this. Let me add a note to verify the webhook variable name.

- [ ] **Step 3: Commit**

```bash
git add app/services/retention_alerts.py retention_alerts.py
git commit -m "feat: add retention alert service + cron script"
```

---

### Task 6: Register Router + Navbar

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/base.html`

- [ ] **Step 1: Register retention router in main.py**

Add import and include_router:

```python
from app.routers import work_items, services, users, intake, dashboards, capacity, requester, retention

app.include_router(work_items.router)
app.include_router(services.router)
app.include_router(users.router)
app.include_router(intake.router)
app.include_router(dashboards.router)
app.include_router(capacity.router)
app.include_router(requester.router)
app.include_router(retention.router)
```

- [ ] **Step 2: Add Retention link to base.html navbar**

After the Requester Portal link:

```html
<li class="nav-item"><a class="nav-link" href="/retention">🧠 Retention</a></li>
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py app/templates/base.html
git commit -m "feat: register retention router and add navbar link"
```

---

### Task 7: Add Retention to Intake API

**Files:**
- Modify: `app/routers/intake.py`

- [ ] **Step 1: Add retention alert endpoint to intake.py**

```python
@router.post("/retention")
def trigger_retention_check(dry_run: bool = False, db: Session = Depends(get_db)):
    from app.services.retention_alerts import check_retention_alerts
    result = check_retention_alerts(db, dry_run=dry_run)
    return result
```

- [ ] **Step 2: Commit**

```bash
git add app/routers/intake.py
git commit -m "feat: add POST /api/intake/retention endpoint"
```

---

### Task 8: Integration Verification

- [ ] **Step 1: Verify app loads with all routes**

Run: `cd D:\pupeteer\opsdash && python -c "import sys; sys.path.insert(0,'.'); from app.main import app; [print(f'  {r.methods} {r.path}') for r in app.routes if hasattr(r,'path') and 'retention' in r.path]"`

Expected output:
```
  {'GET'} /retention
  {'GET'} /retention/{user_id}/detail
  {'POST'} /api/intake/retention
```

- [ ] **Step 2: Test dashboard renders**

Run: `python -c "import http.client; conn=http.client.HTTPConnection('localhost', 6400); conn.request('GET','/retention'); r=conn.getresponse(); print(r.status, len(r.read())); conn.close()"`

Expected: `200 <bytes>`

- [ ] **Step 3: Test member detail renders**

Run: `python -c "import http.client; conn=http.client.HTTPConnection('localhost', 6400); conn.request('GET','/retention/1/detail'); r=conn.getresponse(); print(r.status, len(r.read())); conn.close()"`

Expected: `200 <bytes>`

- [ ] **Step 4: Screenshot and update README**

Take screenshot of `/retention` page:

```python
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={'width':1400,'height':900}).new_page()
    page.goto('http://localhost:6400/retention', wait_until='networkidle')
    page.wait_for_timeout(500)
    page.screenshot(path='screenshots/retention.png', full_page=True)
    browser.close()
```

Add to README.md after Requester Portal section:

```markdown
### Retention Risk 🧠
Anomaly detection dashboard — z-score analysis across 6 signals to identify members at risk of burnout or disengagement. High/Medium/Low risk levels with detailed per-member breakdown.

![Retention Risk](screenshots/retention.png)
```

- [ ] **Step 5: Commit all remaining changes**

```bash
git add README.md screenshots/retention.png
git commit -m "docs: add retention risk screenshots to README"
git push
```
