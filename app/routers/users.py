from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.templates import TemplateResponse

router = APIRouter()


@router.get("/users")
def list_users(request: Request, db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.display_name).all()
    return TemplateResponse("users.html", {"request": request, "users": users})


@router.post("/users")
def create_user(
    display_name: str = Form(...),
    email: str = Form(...),
    role: str = Form("member"),
    db: Session = Depends(get_db),
):
    user = User(display_name=display_name, email=email, role=role)
    db.add(user)
    db.commit()
    return RedirectResponse(url="/users", status_code=303)


@router.post("/users/{user_id}/delete")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        db.delete(user)
        db.commit()
    return RedirectResponse(url="/users", status_code=303)
