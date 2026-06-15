from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import role_required
from app.config import AI_REVIEW_ENABLED, AI_REVIEW_MODEL, OPENAI_API_KEY
from app.database import get_db
from app.models import AIReview, Service, User, WorkItem
from app.services.ai_review import apply_review, create_or_refresh_review
from app.templates import TemplateResponse

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("")
def review_queue(request: Request, state: str = "pending", db: Session = Depends(get_db)):
    reviews = db.query(AIReview).filter(AIReview.state == state).order_by(AIReview.created_at.desc()).all()
    services = db.query(Service).filter(Service.status == "active").order_by(Service.name).all()
    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()
    return TemplateResponse("reviews.html", {
        "request": request,
        "reviews": reviews,
        "services": services,
        "users": users,
        "state": state,
        "ai_enabled": AI_REVIEW_ENABLED and bool(OPENAI_API_KEY),
        "ai_model": AI_REVIEW_MODEL,
    })


@router.post("/work-items/{item_id}/analyze")
def analyze_work_item(item_id: int, use_ai: bool = Form(True), db: Session = Depends(get_db), _=Depends(role_required("leader", "admin"))):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        create_or_refresh_review(db, item, use_ai=use_ai)
    return RedirectResponse(url="/reviews", status_code=303)


@router.post("/{review_id}/approve")
def approve_review(
    review_id: int,
    status: str = Form(...),
    service_id: Optional[int] = Form(None),
    assignee_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    _=Depends(role_required("leader", "admin")),
):
    review = db.query(AIReview).filter(AIReview.id == review_id).first()
    if review and review.state == "pending":
        apply_review(db, review, status, service_id, assignee_id)
    return RedirectResponse(url="/reviews", status_code=303)


@router.post("/{review_id}/reject")
def reject_review(review_id: int, db: Session = Depends(get_db), _=Depends(role_required("leader", "admin"))):
    review = db.query(AIReview).filter(AIReview.id == review_id).first()
    if review and review.state == "pending":
        review.state = "rejected"
        review.reviewed_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(url="/reviews", status_code=303)
