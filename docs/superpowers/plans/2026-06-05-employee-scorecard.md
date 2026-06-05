# Employee Scorecard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quarterly/yearly scorecard ranking team members across 7 criteria with CSV export.

**Architecture:** All metrics computed on-the-fly from existing WorkItem, Capacity, RetentionScore tables. Period model (quarter/year) with date range computation. 7 independent metric functions feed into a ranking engine.

**Tech Stack:** FastAPI, SQLAlchemy, Jinja2, Bootstrap 5, Python statistics

---

### Task 1: Performance Scoring Service

**Files:**
- Create: `app/services/performance.py`

- [ ] **Step 1: Create performance.py with all metric + ranking logic**

```python
from datetime import datetime, timezone
from calendar import monthrange
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import func, case, and_
from sqlalchemy.orm import Session

from app.models import User, WorkItem, Capacity, RetentionScore


@dataclass
class Period:
    type: str  # "quarter" or "year"
    year: int
    quarter: Optional[int] = None  # 1-4, None if year

    def label(self) -> str:
        if self.type == "quarter":
            return f"Q{self.quarter} {self.year}"
        return f"Year {self.year}"

    def key(self) -> str:
        if self.type == "quarter":
            return f"{self.year}-Q{self.quarter}"
        return f"{self.year}"

    def date_range(self):
        """Return (start_date, end_date) for this period."""
        if self.type == "quarter":
            start_month = (self.quarter - 1) * 3 + 1
            end_month = start_month + 2
            start = datetime(self.year, start_month, 1, tzinfo=timezone.utc)
            _, last = monthrange(self.year, end_month)
            end = datetime(self.year, end_month, last, 23, 59, 59, tzinfo=timezone.utc)
        else:
            start = datetime(self.year, 1, 1, tzinfo=timezone.utc)
            end = datetime(self.year, 12, 31, 23, 59, 59, tzinfo=timezone.utc)
        return start, end

    def previous(self):
        """Return the previous period of same type."""
        if self.type == "quarter":
            q = self.quarter - 1
            y = self.year
            if q < 1:
                q = 4
                y -= 1
            return Period("quarter", y, q)
        return Period("year", self.year - 1)


def get_active_users(db: Session):
    return db.query(User).filter(User.is_active == True).all()


def count_done(db: Session, user_id: int, start, end):
    return db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
    ).scalar() or 0


def avg_cycle_time(db: Session, user_id: int, start, end):
    avg = db.query(
        func.avg(func.julianday(WorkItem.completed_at) - func.julianday(WorkItem.created_at))
    ).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
    ).scalar()
    return float(avg) if avg else 0.0


def reliability_score(db: Session, user_id: int, start, end):
    total = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    if total == 0:
        return 1.0
    blocked = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Blocked",
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    return 1.0 - (blocked / total)


def versatility_score(db: Session, user_id: int, start, end):
    types = db.query(func.count(func.distinct(WorkItem.work_type))).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0
    services = db.query(func.count(func.distinct(WorkItem.service_id))).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
        WorkItem.service_id.isnot(None),
    ).scalar() or 0
    return types + services


def dedication_score(db: Session, user_id: int, start, end):
    total_items = db.query(func.count(WorkItem.id)).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.created_at >= start,
        WorkItem.created_at <= end,
    ).scalar() or 0

    # Sum leave + meeting hours across months in period
    if start.year == end.year and start.month == end.month:
        months_in_period = [(start.year, start.month)]
    else:
        months_in_period = []
        y, m = start.year, start.month
        while (y, m) <= (end.year, end.month):
            months_in_period.append((y, m))
            m += 1
            if m > 12:
                m = 1
                y += 1

    leave_total = 0.0
    meeting_total = 0.0
    for y, m in months_in_period:
        key = f"{y}-{m:02d}"
        cap = db.query(Capacity).filter(
            Capacity.user_id == user_id,
            Capacity.month == key,
        ).first()
        if cap:
            leave_total += float(cap.leave_hours or 0)
            meeting_total += float(cap.meeting_hours or 0)

    divisor = leave_total + meeting_total + 1
    return total_items / divisor


def improvement_score(db: Session, user_id: int, period: Period):
    current_start, current_end = period.date_range()
    current_done = count_done(db, user_id, current_start, current_end)

    prev = period.previous()
    prev_start, prev_end = prev.date_range()
    prev_done = count_done(db, user_id, prev_start, prev_end)

    if prev_done == 0:
        return 1.0 if current_done > 0 else 0.0
    return current_done / prev_done


def risk_improvement_score(db: Session, user_id: int, period: Period):
    """Return risk improvement points. Positive = improvement."""
    current_start, current_end = period.date_range()
    prev = period.previous()
    prev_start, prev_end = prev.date_range()

    current_scores = db.query(RetentionScore).filter(
        RetentionScore.user_id == user_id,
        RetentionScore.created_at >= current_start,
        RetentionScore.created_at <= current_end,
    ).order_by(RetentionScore.created_at.desc()).all()

    prev_scores = db.query(RetentionScore).filter(
        RetentionScore.user_id == user_id,
        RetentionScore.created_at >= prev_start,
        RetentionScore.created_at <= prev_end,
    ).order_by(RetentionScore.created_at.desc()).all()

    risk_values = {"Low": 0, "Medium": 1, "High": 2}
    current_risk = risk_values.get(current_scores[0].risk_level, 0) if current_scores else 0
    prev_risk = risk_values.get(prev_scores[0].risk_level, 0) if prev_scores else 0

    improvement = prev_risk - current_risk  # positive = getting better
    return improvement


def compute_metrics(db: Session, user: User, period: Period):
    start, end = period.date_range()
    return {
        "productivity": count_done(db, user.id, start, end),
        "efficiency": avg_cycle_time(db, user.id, start, end),
        "reliability": reliability_score(db, user.id, start, end),
        "versatility": versatility_score(db, user.id, start, end),
        "improvement": improvement_score(db, user.id, period),
        "dedication": dedication_score(db, user.id, start, end),
        "risk_improvement": risk_improvement_score(db, user.id, period),
    }


METRIC_CONFIG = {
    "productivity": {"lower_better": False, "label": "Productivity"},
    "efficiency": {"lower_better": True, "label": "Efficiency"},
    "reliability": {"lower_better": False, "label": "Reliability"},
    "versatility": {"lower_better": False, "label": "Versatility"},
    "improvement": {"lower_better": False, "label": "Improvement"},
    "dedication": {"lower_better": False, "label": "Dedication"},
    "risk_improvement": {"lower_better": False, "label": "Risk Improvement"},
}


def rank_metric(values: list, lower_better: bool):
    """Rank a list of (user_id, value) tuples. Returns dict of user_id -> rank."""
    sorted_vals = sorted(values, key=lambda x: x[1], reverse=not lower_better)
    ranks = {}
    current_rank = 1
    for i, (uid, val) in enumerate(sorted_vals):
        if i > 0 and val != sorted_vals[i - 1][1]:
            current_rank = i + 1
        ranks[uid] = current_rank
    return ranks


def compute_performance(db: Session, period: Period):
    users = get_active_users(db)
    if not users:
        return []

    # Compute metrics for all users
    all_metrics = {}
    for user in users:
        all_metrics[user.id] = {
            "user": user,
            "metrics": compute_metrics(db, user, period),
        }

    # Rank each metric
    metric_ranks = {}
    for metric_name, config in METRIC_CONFIG.items():
        values = [(uid, m["metrics"][metric_name]) for uid, m in all_metrics.items()]
        metric_ranks[metric_name] = rank_metric(values, config["lower_better"])

    # Build results
    results = []
    for uid, m in all_metrics.items():
        ranks = {name: metric_ranks[name][uid] for name in METRIC_CONFIG}
        overall = sum(ranks.values())
        results.append({
            "user": m["user"],
            "values": m["metrics"],
            "ranks": ranks,
            "overall_score": overall,
        })

    # Sort by overall score (lower = better), tiebreak by productivity rank
    results.sort(key=lambda r: (r["overall_score"], r["ranks"]["productivity"]))

    # Assign overall rank
    for i, r in enumerate(results):
        r["overall_rank"] = i + 1

    return results


def get_available_periods(db: Session) -> list[Period]:
    """Detect periods that have work item data."""
    first = db.query(func.min(WorkItem.created_at)).scalar()
    if not first:
        return [Period("quarter", datetime.now(timezone.utc).year, 1)]

    fy = first.year
    ny = datetime.now(timezone.utc).year
    periods = []
    for y in range(fy, ny + 1):
        periods.append(Period("year", y))
        for q in range(1, 5):
            periods.append(Period("quarter", y, q))
    return periods
```

- [ ] **Step 2: Verify import**

Run: `cd D:\pupeteer\opsdash && python -c "import sys; sys.path.insert(0,'.'); from app.services.performance import compute_performance, Period; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add app/services/performance.py
git commit -m "feat: add performance scoring service with 7 metric calculators"
```

---

### Task 2: Performance Router

**Files:**
- Create: `app/routers/performance.py`

- [ ] **Step 1: Create the router**

```python
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import csv
import io

from app.database import get_db
from app.models import User
from app.services.performance import compute_performance, get_available_periods, Period
from app.templates import TemplateResponse

router = APIRouter(prefix="/performance", tags=["performance"])


def parse_period(s: str) -> Period:
    """Parse '2026-Q1' or '2026' into a Period."""
    if "-Q" in s:
        parts = s.split("-Q")
        return Period("quarter", int(parts[0]), int(parts[1]))
    return Period("year", int(s))


@router.get("")
def performance_dashboard(
    request: Request,
    period: str = Query(default=None),
    db: Session = Depends(get_db),
):
    available = get_available_periods(db)
    if not available:
        available = [Period("quarter", 2026, 1)]

    # Default to latest quarter
    if not period:
        period = available[-1].key()

    current_period = parse_period(period)
    results = compute_performance(db, current_period)

    # Category winners (best rank 1 in each metric)
    metric_config = {
        "productivity": "🏆 Productivity",
        "efficiency": "⚡ Efficiency",
        "reliability": "🛡 Reliability",
        "versatility": "🎯 Versatility",
        "improvement": "📈 Improvement",
        "dedication": "💪 Dedication",
        "risk_improvement": "🤖 Risk Improvement",
    }
    winners = {}
    for key in metric_config:
        for r in results:
            if r["ranks"][key] == 1:
                winners[key] = r["user"].display_name
                break

    return TemplateResponse("performance.html", {
        "request": request,
        "results": results,
        "current_period": current_period,
        "available_periods": available,
        "metric_config": metric_config,
        "winners": winners,
    })


@router.get("/export")
def export_performance(
    period: str = Query(default=None),
    db: Session = Depends(get_db),
):
    available = get_available_periods(db)
    if not period:
        period = available[-1].key() if available else "2026-Q1"

    current_period = parse_period(period)
    results = compute_performance(db, current_period)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Rank", "Member", "Productivity", "Efficiency", "Reliability",
                     "Versatility", "Improvement", "Dedication", "Risk Improvement", "Overall Score"])
    for r in results:
        v = r["values"]
        writer.writerow([
            r["overall_rank"],
            r["user"].display_name,
            v["productivity"],
            f'{v["efficiency"]:.1f}',
            f'{v["reliability"]:.2f}',
            v["versatility"],
            f'{v["improvement"]:.2f}',
            f'{v["dedication"]:.1f}',
            v["risk_improvement"],
            r["overall_score"],
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=scorecard-{current_period.key()}.csv"},
    )
```

- [ ] **Step 2: Verify import**

Run: `cd D:\pupeteer\opsdash && python -c "import sys; sys.path.insert(0,'.'); from app.routers.performance import router; print('OK')"`

- [ ] **Step 3: Commit**

```bash
git add app/routers/performance.py
git commit -m "feat: add performance router with dashboard + CSV export"
```

---

### Task 3: Performance Template

**Files:**
- Create: `app/templates/performance.html`

- [ ] **Step 1: Create the template**

```html
{% extends "base.html" %}
{% block title %}Employee Scorecard{% endblock %}
{% block content %}

<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>🏆 Employee Scorecard — {{ current_period.label() }}</h2>
  <div>
    <a href="/performance/export?period={{ current_period.key() }}" class="btn btn-outline-success btn-sm">CSV</a>
  </div>
</div>

<form method="GET" class="row g-2 mb-4">
  <div class="col-auto">
    <select name="period" class="form-select" onchange="this.form.submit()">
      {% for p in available_periods %}
      <option value="{{ p.key() }}" {{ 'selected' if p.key() == current_period.key() }}>{{ p.label() }}</option>
      {% endfor %}
    </select>
  </div>
</form>

{% if results %}
<div class="table-responsive">
  <table class="table table-hover align-middle">
    <thead class="table-dark">
      <tr>
        <th>#</th>
        <th>Member</th>
        {% for key, label in metric_config.items() %}
        <th class="text-center" title="{{ label }}">{{ label.split(' ')[0] }}</th>
        {% endfor %}
        <th class="text-center">🎯 Overall</th>
      </tr>
    </thead>
    <tbody>
      {% for r in results %}
      {% set medal = '🥇' if r.overall_rank == 1 else '🥈' if r.overall_rank == 2 else '🥉' if r.overall_rank == 3 else '' %}
      {% set medal_class = 'table-warning' if r.overall_rank <= 3 else '' %}
      <tr class="{{ medal_class }}">
        <td><strong>{{ medal }}{{ r.overall_rank }}</strong></td>
        <td><a href="/users/{{ r.user.id }}" class="text-decoration-none fw-bold">{{ r.user.display_name }}</a></td>
        <td class="text-center">{{ r.ranks.productivity }}</td>
        <td class="text-center">{{ r.ranks.efficiency }}</td>
        <td class="text-center">{{ r.ranks.reliability }}</td>
        <td class="text-center">{{ r.ranks.versatility }}</td>
        <td class="text-center">{{ r.ranks.improvement }}</td>
        <td class="text-center">{{ r.ranks.dedication }}</td>
        <td class="text-center">{{ r.ranks.risk_improvement }}</td>
        <td class="text-center"><strong>{{ r.overall_score }}</strong></td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<div class="mt-4 p-3 bg-light rounded">
  <h6>🏆 Category Winners</h6>
  <div class="row g-2">
    {% for key, label in metric_config.items() %}
    <div class="col-md-4">
      <small><strong>{{ label }}</strong>: {{ winners.get(key, '-') }}</small>
    </div>
    {% endfor %}
  </div>
</div>

<div class="mt-3 small text-muted">
  <p class="mb-0">Ranking: mỗi tiêu chí xếp hạng 1-N. Overall = tổng các rank (thấp nhất = tốt nhất). 🥇🥈🥉 = Top 3 overall.</p>
</div>

{% else %}
<p class="text-muted text-center">No performance data for this period.</p>
{% endif %}

{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/performance.html
git commit -m "feat: add performance scorecard template"
```

---

### Task 4: Register Router + Navbar

**Files:**
- Modify: `app/main.py`
- Modify: `app/templates/base.html`

- [ ] **Step 1: Register in main.py**

Add `performance` to the import and include_router:

```python
from app.routers import work_items, services, users, intake, dashboards, capacity, requester, retention, performance

app.include_router(work_items.router)
app.include_router(services.router)
app.include_router(users.router)
app.include_router(intake.router)
app.include_router(dashboards.router)
app.include_router(capacity.router)
app.include_router(requester.router)
app.include_router(retention.router)
app.include_router(performance.router)
```

- [ ] **Step 2: Add nav link in base.html**

After the Retention nav link, add:

```html
<li class="nav-item"><a class="nav-link" href="/performance">🏆 Scorecard</a></li>
```

- [ ] **Step 3: Commit**

```bash
git add app/main.py app/templates/base.html
git commit -m "feat: register performance router and add navbar link"
```

---

### Task 5: Integration Verification

- [ ] **Step 1: Verify routes load**

Run: `cd D:\pupeteer\opsdash && python -c "import sys; sys.path.insert(0,'.'); from app.main import app; [print(r.path) for r in app.routes if hasattr(r,'path') and 'performance' in r.path]"`

Expected:
```
/performance
/performance/export
```

- [ ] **Step 2: Start server and test**

```bash
cd D:\pupeteer\opsdash
python -m uvicorn app.main:app --host 0.0.0.0 --port 6400
```

In another terminal:

```bash
curl http://localhost:6400/performance -o D:\pupeteer\opsdash\screenshots\performance_raw.txt
# Check status
curl -s -o /dev/null -w "%{http_code}" http://localhost:6400/performance
```

Expected: 200

- [ ] **Step 3: Take screenshot and update README**

Screenshot the `/performance` page and add to README.

```markdown
### Employee Scorecard 🏆
Quarterly/yearly scorecard ranking members across 7 criteria: Productivity, Efficiency, Reliability, Versatility, Improvement, Dedication, and Risk Improvement. CSV export available.

![Employee Scorecard](screenshots/performance.png)
```

- [ ] **Step 4: Commit everything**

```bash
git add README.md screenshots/performance.png
git commit -m "docs: add employee scorecard screenshots to README"
git push
```
