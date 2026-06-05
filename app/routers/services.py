from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service
from app.templates import TemplateResponse

router = APIRouter()


@router.get("/services")
def list_services(request: Request, db: Session = Depends(get_db)):
    services = db.query(Service).order_by(Service.name).all()
    return TemplateResponse("services.html", {"request": request, "services": services})


@router.post("/services")
def create_service(name: str = Form(...), category: str = Form(None), db: Session = Depends(get_db)):
    service = Service(name=name, category=category)
    db.add(service)
    db.commit()
    return RedirectResponse(url="/services", status_code=303)


@router.post("/services/{service_id}/delete")
def delete_service(service_id: int, db: Session = Depends(get_db)):
    service = db.query(Service).filter(Service.id == service_id).first()
    if service:
        db.delete(service)
        db.commit()
    return RedirectResponse(url="/services", status_code=303)
