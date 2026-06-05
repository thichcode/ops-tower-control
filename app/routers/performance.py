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

    if not period:
        period = available[-1].key()

    current_period = parse_period(period)
    results = compute_performance(db, current_period)

    metric_config = {
        "productivity": "🏆 Productivity",
        "efficiency": "⚡ Efficiency",
        "reliability": "🛡 Reliability",
        "versatility": "🎯 Versatility",
        "improvement": "📈 Improvement",
        "dedication": "💪 Dedication",
        "risk_improvement": "🤖 Risk Improvement",
    }

    # Category winners (best rank 1 in each metric)
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
