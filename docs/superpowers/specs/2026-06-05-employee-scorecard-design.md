# Outstanding Employee Scorecard — Design Spec

## Overview

Compute a quarterly/yearly scorecard ranking team members across 7 criteria. Each criterion ranks members 1 to N. Overall score = sum of ranks (lowest wins). Top 3 highlighted with gold/silver/bronze.

## Period System

- **Quarterly**: Q1 (Jan-Mar), Q2 (Apr-Jun), Q3 (Jul-Sep), Q4 (Oct-Dec)
- **Yearly**: Full year (e.g., 2026)
- Previous period auto-computed for Improvement and Risk criteria

## 7 Criteria

| # | Criterion | Metric | Lower is better? | Data Source |
|:-:|-----------|--------|:----------------:|-------------|
| 1 | Productivity | COUNT of items marked Done in period | No | WorkItem.status, completed_at |
| 2 | Efficiency | AVG(completed_at - created_at) in days for Done items | Yes | WorkItem.completed_at, created_at |
| 3 | Reliability | % of items NOT Blocked = 1 - (blocked / total) | No | WorkItem.status |
| 4 | Versatility | COUNT(DISTINCT work_type) + COUNT(DISTINCT service_id) | No | WorkItem.work_type, service_id |
| 5 | Improvement | Throughput this period / Throughput previous period | No | WorkItem.completed_at |
| 6 | Dedication | Total items / (leave_hours + meeting_hours + 1) | No | WorkItem + Capacity |
| 7 | Risk Improvement | Risk level change from previous period (High→Low = +2, Medium→Low = +1, etc.) | No | RetentionScore |

### Risk Improvement Scoring
- High → Low: +3 points
- High → Medium: +2 points
- Medium → Low: +2 points
- No change: 0 points
- Any increase (Low→Medium, etc.): -1 point
- No previous data: 0 points

## Ranking Method

For each criterion:
1. Sort members by the metric value
2. Assign rank 1 to best, rank 2 to second, etc.
3. Ties get same rank (e.g., two members tied for 1st both get rank 1, next gets rank 3)

**Overall**: SUM of all 7 ranks. Lowest overall = best employee.

**Tiebreaker**: If two members have same overall rank, compare by Productivity rank.

## Dashboard

- **URL**: `/performance`
- **Period selector**: Dropdown with all available quarters + years
- **Table columns**: Member | 🏆 Prod | ⚡ Eff | 🛡 Rel | 🎯 Ver | 📈 Imp | 💪 Ded | 🤖 Risk | Overall
- Each cell shows rank number
- Top 3 highlighted: 🥇 gold (#FFD700), 🥈 silver (#C0C0C0), 🥉 bronze (#CD7F32)
- Summary row: shows which member won each criterion
- **Export CSV**: `/performance/export?period=2026-Q1`

## Data Model

No new database model needed — all computed on-the-fly from existing WorkItem, Capacity, RetentionScore tables.

Computing 3 months of data for all active members involves ~20 queries total (batch queries per criterion). Acceptable for on-demand dashboard.

## New Files

- `app/services/performance.py` — compute all metrics + rankings for a period
- `app/routers/performance.py` — dashboard + CSV export
- `app/templates/performance.html` — scorecard table
- `performance_report.py` — root level cron script (optional)

## Modified Files

- `app/main.py` — register performance router
- `app/templates/base.html` — add Performance nav link

## Scoring Service Interface

```python
class Period:
    type: str  # "quarter" or "year"
    year: int
    quarter: int | None  # None if type == "year"

def compute_performance(db, period: Period) -> list[dict]:
    """
    Returns list of dicts sorted by overall rank:
    [
        {
            "user": User,
            "ranks": {"productivity": 1, "efficiency": 3, ...},
            "values": {"productivity": 42, "efficiency": 2.5, ...},
            "overall_rank": 1,
            "overall_score": 15,
        },
        ...
    ]
    """

def get_available_periods(db) -> list[Period]:
    """Return list of periods that have data."""
```

## Out of Scope

- Team-wide averages / benchmark comparisons
- Historical trend charts per criterion
- Automated Teams report (can be added later via performance_report.py)
- Manager review/approval workflow
