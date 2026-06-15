from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import authenticate_user, hash_password, get_current_user
from app.database import get_db
from app.models import User
from app.templates import TemplateResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def login_form(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=303)
    return TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    user = authenticate_user(db, email, password)
    if not user:
        return TemplateResponse("login.html", {"request": request, "error": "Invalid email or password"})
    request.session["user_id"] = user.id
    request.session["user_role"] = user.role
    next_url = request.query_params.get("next") or "/"
    return RedirectResponse(url=next_url, status_code=303)


@router.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/auth/login", status_code=303)


@router.get("/profile")
def profile(request: Request, current_user: User | None = Depends(get_current_user), db: Session = Depends(get_db)):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)
    return TemplateResponse("login.html", {
        "request": request,
        "user": current_user,
        "error": None,
        "profile_mode": True,
    })


@router.post("/profile/password")
def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    current_user: User | None = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not current_user:
        return RedirectResponse(url="/auth/login", status_code=303)
    from app.auth import verify_password
    if not verify_password(current_password, current_user.password_hash or ""):
        return TemplateResponse("login.html", {
            "request": request,
            "user": current_user,
            "error": "Current password is incorrect",
            "profile_mode": True,
        })
    current_user.password_hash = hash_password(new_password)
    db.commit()
    return TemplateResponse("login.html", {
        "request": request,
        "user": current_user,
        "error": None,
        "profile_mode": True,
        "success": "Password updated",
    })
