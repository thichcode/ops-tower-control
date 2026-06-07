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


@router.get("/export/reward")
def export_reward_report(
    period: str = Query(default=None),
    db: Session = Depends(get_db),
):
    """Boss-facing reward proposal report (Vietnamese)."""
    from datetime import datetime
    from app.services.performance import METRIC_CONFIG

    available = get_available_periods(db)
    if not period:
        period = available[-1].key() if available else "2026-Q1"

    current_period = parse_period(period)
    results = compute_performance(db, current_period)

    # Team averages for baseline
    team_size = len(results)
    team_avg = {}
    for key in METRIC_CONFIG:
        vals = [r["values"][key] for r in results if r["values"][key] is not None]
        team_avg[key] = sum(vals) / len(vals) if vals else 0

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["BÁO CÁO ĐỀ XUẤT KHEN THƯỞNG NHÂN SỰ"])
    writer.writerow([])
    writer.writerow(["Kỳ đánh giá", current_period.label()])
    writer.writerow(["Ngày lập", datetime.now().strftime("%d/%m/%Y %H:%M")])
    writer.writerow(["Số nhân sự", team_size])
    writer.writerow(["Hệ thống", "Ops Control Tower — auto-generated"])
    writer.writerow([])
    writer.writerow([
        "#", "Họ và tên", "Tổng điểm", "Task hoàn thành",
        "TG xử lý TB (ngày)", "Tỷ lệ đạt (%)", "Đa năng",
        "Δ kỳ trước (%)", "Điểm mạnh", "% vs TB team", "Đề xuất",
    ])

    # Top 3 = bonus, Bottom 3 = support
    top_3_ids = {r["user"].id for r in results[:3]}
    bottom_3_ids = {r["user"].id for r in results[-3:]} if team_size >= 3 else set()

    for r in results:
        v = r["values"]
        user_id = r["user"].id
        overall_rank = r["overall_rank"]
        medal = "🥇" if overall_rank == 1 else "🥈" if overall_rank == 2 else "🥉" if overall_rank == 3 else ""

        # Improvement delta vs prev period (improvement is ratio: 1.0 = same, 1.2 = +20%)
        improvement_pct = round((v["improvement"] - 1.0) * 100, 1) if v["improvement"] else 0
        improvement_str = f"{'+' if improvement_pct >= 0 else ''}{improvement_pct}%"

        # Top 2 strengths (best rank = lowest rank number)
        ranked_metrics = sorted(METRIC_CONFIG.items(), key=lambda x: r["ranks"][x[0]])
        top_strengths = ", ".join([ranked_metrics[i][1]["label"] for i in range(min(2, len(ranked_metrics)))])

        # % vs team avg on productivity
        team_prod_avg = team_avg["productivity"]
        prod_pct = round((v["productivity"] / team_prod_avg - 1) * 100, 1) if team_prod_avg > 0 else 0
        prod_pct_str = f"{'+' if prod_pct >= 0 else ''}{prod_pct}%"

        # Recommendation
        if user_id in top_3_ids:
            recommendation = f"{medal} Đề xuất khen thưởng"
        elif user_id in bottom_3_ids:
            recommendation = "Cần hỗ trợ thêm"
        else:
            recommendation = "Đạt chuẩn"

        writer.writerow([
            overall_rank,
            r["user"].display_name,
            r["overall_score"],
            v["productivity"],
            f'{v["efficiency"]:.1f}',
            f'{v["reliability"] * 100:.1f}%',
            v["versatility"],
            improvement_str,
            top_strengths,
            prod_pct_str,
            recommendation,
        ])

    # Footer
    writer.writerow([])
    writer.writerow(["--- Phần duyệt ---"])
    writer.writerow([])
    writer.writerow(["Người lập báo cáo", "", "Trưởng phòng", "", "Ban giám đốc"])
    writer.writerow(["(Ký, ghi rõ họ tên)", "", "(Ký, ghi rõ họ tên)", "", "(Ký, ghi rõ họ tên)"])
    writer.writerow([])
    writer.writerow(["Ngày", "", "Ngày", "", "Ngày"])
    writer.writerow([])
    writer.writerow(["Ghi chú", "Báo cáo tự động từ Ops Control Tower dựa trên dữ liệu work items thực tế."])

    output.seek(0)
    csv_text = "\ufeff" + output.getvalue()  # UTF-8 BOM for Excel
    return StreamingResponse(
        iter([csv_text]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=de-xuat-thuong-{current_period.key()}.csv"},
    )
