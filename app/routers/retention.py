from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, RetentionScore
from app.services.retention import compute_all_scores, compute_member_scores
from app.templates import TemplateResponse

router = APIRouter(prefix="/retention", tags=["retention"])


@router.get("")
def retention_dashboard(request: Request, db: Session = Depends(get_db)):
    compute_all_scores(db)

    scores = db.query(RetentionScore).all()

    members = {}
    for s in scores:
        if s.user_id not in members:
            user = db.query(User).filter(User.id == s.user_id).first()
            members[s.user_id] = {"user": user, "current": s, "history": []}
        members[s.user_id]["history"].append(s)
        if s.created_at > members[s.user_id]["current"].created_at:
            members[s.user_id]["current"] = s

    risk_order = {"High": 0, "Medium": 1, "Low": 2}
    sorted_members = sorted(
        members.values(),
        key=lambda m: (risk_order.get(m["current"].risk_level, 3), -m["current"].flag_count),
    )

    return TemplateResponse("retention.html", {"request": request, "members": sorted_members})


@router.get("/{user_id}/detail")
def retention_detail(user_id: int, request: Request, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return TemplateResponse("retention.html", {"request": request, "members": []})

    compute_member_scores(db, user_id)
    history = db.query(RetentionScore).filter(
        RetentionScore.user_id == user_id,
    ).order_by(RetentionScore.created_at.desc()).limit(6).all()

    return TemplateResponse("retention_detail.html", {
        "request": request,
        "member": user,
        "history": history,
    })
