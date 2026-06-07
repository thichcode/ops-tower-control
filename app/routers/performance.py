from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
import csv
import io
from datetime import datetime, timezone

from app.database import get_db
from app.models import User, WorkItem, Service
from app.services.performance import compute_performance, get_available_periods, Period
from app.templates import TemplateResponse

router = APIRouter(prefix="/performance", tags=["performance"])


def parse_period(s: str) -> Period:
    """Parse '2026-Q1' or '2026' into a Period."""
    if "-Q" in s:
        parts = s.split("-Q")
        return Period("quarter", int(parts[0]), int(parts[1]))
    return Period("year", int(s))


def get_crisis_resolver_tasks(db: Session, user_id: int, start, end, limit: int = 2) -> list:
    """Top Done items on critical services (K8s/Cloudflare/Backup) for a user."""
    critical_names = {"Kubernetes", "Cloudflare", "Backup"}
    critical_services = db.query(Service).filter(Service.name.in_(critical_names)).all()
    critical_ids = [s.id for s in critical_services]
    if not critical_ids:
        return []

    items = db.query(WorkItem).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.service_id.in_(critical_ids),
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
        WorkItem.completed_at.isnot(None),
        WorkItem.created_at.isnot(None),
    ).all()

    items_with_cycle = []
    for item in items:
        completed = item.completed_at.replace(tzinfo=timezone.utc) if item.completed_at.tzinfo is None else item.completed_at
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        cycle = (completed - created).total_seconds() / 86400
        items_with_cycle.append({
            "title": item.title,
            "service": item.service.name if item.service else "-",
            "cycle_days": round(cycle, 1),
        })

    items_with_cycle.sort(key=lambda x: x["cycle_days"])
    return items_with_cycle[:limit]


def get_speed_demon_tasks(db: Session, user_id: int, start, end, limit: int = 2) -> list:
    """Fastest Done items for a user (lowest cycle time)."""
    items = db.query(WorkItem).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
        WorkItem.completed_at.isnot(None),
        WorkItem.created_at.isnot(None),
    ).all()

    items_with_cycle = []
    for item in items:
        completed = item.completed_at.replace(tzinfo=timezone.utc) if item.completed_at.tzinfo is None else item.completed_at
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        cycle = (completed - created).total_seconds() / 86400
        if cycle < 0:
            continue
        items_with_cycle.append({
            "title": item.title,
            "service": item.service.name if item.service else "-",
            "cycle_days": round(cycle, 1),
        })

    items_with_cycle.sort(key=lambda x: x["cycle_days"])
    return items_with_cycle[:limit]


def get_versatility_star_tasks(db: Session, user_id: int, start, end, limit: int = 2) -> list:
    """Most diverse services worked on — show 1 sample task per service."""
    items = db.query(WorkItem).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
        WorkItem.service_id.isnot(None),
    ).all()

    by_service = {}
    for item in items:
        svc = item.service.name if item.service else None
        if svc and svc not in by_service:
            by_service[svc] = item.title

    samples = [{"title": title, "service": svc} for svc, title in by_service.items()]
    return samples[:limit]


def get_most_improved_tasks(db: Session, user_id: int, start, end, limit: int = 2) -> list:
    """Tasks completed in current period that didn't exist in prev — show recent Done items."""
    items = db.query(WorkItem).filter(
        WorkItem.assignee_id == user_id,
        WorkItem.status == "Done",
        WorkItem.completed_at >= start,
        WorkItem.completed_at <= end,
    ).order_by(WorkItem.completed_at.desc()).limit(limit).all()

    return [
        {
            "title": item.title,
            "service": item.service.name if item.service else "-",
            "cycle_days": "—",
        }
        for item in items
    ]


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
    from app.services.performance import METRIC_CONFIG

    available = get_available_periods(db)
    if not period:
        period = available[-1].key() if available else "2026-Q1"

    current_period = parse_period(period)
    results = compute_performance(db, current_period)
    period_start, period_end = current_period.date_range()

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

    # === Standout Tasks Section ===
    writer.writerow([])
    writer.writerow(["--- TASK NỔI BẬT (bằng chứng cụ thể) ---"])
    writer.writerow([])

    # Find top performer in each category (lowest rank number = best)
    # Crisis Resolver: top 3 by productivity
    crisis_top = sorted(results, key=lambda x: x["ranks"]["productivity"])[:3]
    # Speed Demon: top 3 by efficiency (lower better)
    speed_top = sorted(results, key=lambda x: x["ranks"]["efficiency"])[:3]
    # Versatility Star: top 3 by versatility
    versatile_top = sorted(results, key=lambda x: x["ranks"]["versatility"])[:3]
    # Most Improved: top 3 by improvement
    improved_top = sorted(results, key=lambda x: x["ranks"]["improvement"])[:3]

    for category_label, category_top, task_extractor in [
        ("🚨 CRISIS RESOLVER (giải quyết sự cố nghiêm trọng)", crisis_top, get_crisis_resolver_tasks),
        ("⚡ SPEED DEMON (xử lý nhanh)", speed_top, get_speed_demon_tasks),
        ("🎯 VERSATILITY STAR (đa năng, đa dịch vụ)", versatile_top, get_versatility_star_tasks),
        ("📈 MOST IMPROVED (tiến bộ vượt bậc)", improved_top, get_most_improved_tasks),
    ]:
        writer.writerow([category_label])
        writer.writerow(["Thành viên", "Service", "Task", "Thời gian xử lý (ngày)"])
        for r in category_top:
            tasks = task_extractor(db, r["user"].id, period_start, period_end, limit=2)
            if not tasks:
                writer.writerow([r["user"].display_name, "-", "(không có task trong kỳ)", "-"])
                continue
            for i, t in enumerate(tasks):
                writer.writerow([
                    r["user"].display_name if i == 0 else "",
                    t.get("service", "-"),
                    t["title"][:60] + ("…" if len(t["title"]) > 60 else ""),
                    t.get("cycle_days", "—"),
                ])
        writer.writerow([])

    # Footer
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
