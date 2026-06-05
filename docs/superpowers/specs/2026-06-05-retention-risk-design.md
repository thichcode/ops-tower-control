# Retention Risk Prediction — Design Spec

## Overview

Predict employee turnover risk using anomaly detection (z-score) on existing operational data. No ML model required — purely statistical anomaly detection on member-level metrics.

## Signals & Scoring

For each active member, compute z-scores monthly based on their own historical rolling window:

| Signal | Window | Metric | Z > 2 (risk) | Z < -2 (risk) |
|--------|--------|--------|-------------|-------------|
| Leave hours | 6 months | Current month vs past 6mo mean | Burnout risk | — |
| Throughput | 8 weeks | Avg items/week last 4wk vs prev 8wk | — | Disengagement |
| Cycle time | 3 months | Avg days created→done this month vs past 3mo | Burnout/difficulty | — |
| Utilization % | current month | Demand / available hours | Burnout (>100%) | Disengagement (<30%) |
| Blocked ratio | 3 months | Blocked / total assigned items | Frustration | — |
| Meeting hours | 6 months | Current month vs past 6mo mean | Meeting overload | — |

### Composite Risk Level

- **0-1 flags** (|z| > 2): 🟢 Low
- **2 flags**: 🟡 Medium
- **3+ flags**: 🔴 High
- If any single flag persists 2+ consecutive months → auto-escalate by one level.

## Data Model

```python
class RetentionScore(Base):
    __tablename__ = "retention_scores"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(Text, nullable=False)  # "2026-06"
    risk_level = Column(Text, nullable=False)  # Low / Medium / High
    flag_count = Column(Integer, default=0)
    signals = Column(JSON, nullable=True)  # {"leave_z": 3.1, "throughput_z": -2.4, ...}
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
```

## New Files

- `app/services/retention.py` — compute z-scores, risk levels, save to DB
- `app/services/retention_alerts.py` — Teams alert for risk changes
- `app/routers/retention.py` — dashboard + API routes
- `app/templates/retention.html` — retention dashboard template

## Dashboard (`/retention`)

Card-based layout, each member gets a card sorted by risk level (High → Medium → Low):

- Member name + risk badge (🟢🟡🔴)
- Flagged signals with z-score + sparkline trend
- Historical risk trend (last 6 months mini chart)
- Click to expand per-signal detail charts (throughput, leave, cycle time trends)

## Alert Mechanism

- `POST /api/intake/retention-alerts` triggers check
- Sends Teams card when:
  - Member transitions MEDIUM → HIGH
  - Member has 3+ flags for 2 consecutive months
  - Any member reaches HIGH for the first time
- Follows same pattern as `app/services/leader_alerts.py` / `app/services/notifications.py`

## Registration

- Router: `app/routers/retention.py` → prefix `/retention`
- Navbar: "Retention" link added after "Requester Portal"
- Alert endpoint: `POST /api/intake/retention-alerts` (dry-run mode)
- Cron-ready: `retention_alerts.py` at project root

## Scoring Computation (Z-Score)

```python
def compute_z_score(current_value, historical_values):
    mean = statistics.mean(historical_values)
    stdev = statistics.stdev(historical_values) if len(historical_values) > 1 else 1
    return (current_value - mean) / stdev if stdev > 0 else 0
```

For utilization: special-cased:
- utilization > 100% OR utilization < 30% → flag regardless of z-score
- Otherwise compute z-score normally

## Testing

- Test `compute_z_score` with known inputs
- Test `compute_retention_scores` with seed data
- Test alert trigger logic
- Test dashboard renders 200 with seed data

## Out of Scope

- ML model training — requires labeled exit data, future iteration
- Survey / sentiment integration — pure operational data only
- Individual risk factors outside ops data (manager relationship, compensation, etc.)
