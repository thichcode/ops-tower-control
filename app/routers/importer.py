from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json
import os

from app.database import get_db
from app.models import User, Service, WorkItem
from app.templates import TemplateResponse

router = APIRouter(prefix="/import", tags=["import"])


@router.get("", response_class=HTMLResponse)
def import_page(request: Request):
    return TemplateResponse("import.html", {
        "request": request,
        "result": None,
    })


@router.get("/sample")
def download_sample():
    sample_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "sample-import.json")
    return FileResponse(
        sample_path,
        media_type="application/json",
        filename="sample-import.json",
    )


@router.post("/upload")
async def import_upload(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    if not file.filename.endswith(".json"):
        return TemplateResponse("import.html", {
            "request": request,
            "result": {"success": False, "error": "Only .json files accepted", "imported": 0, "skipped": 0, "errors": []},
        })

    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return TemplateResponse("import.html", {
            "request": request,
            "result": {"success": False, "error": f"Invalid JSON: {e}", "imported": 0, "skipped": 0, "errors": []},
        })

    tasks = data.get("tasks", [])
    if not tasks:
        return TemplateResponse("import.html", {
            "request": request,
            "result": {"success": False, "error": "No 'tasks' array found in JSON", "imported": 0, "skipped": 0, "errors": []},
        })

    imported = 0
    skipped = 0
    errors = []

    for i, task in enumerate(tasks):
        title = (task.get("title") or "").strip()
        if not title:
            errors.append(f"Task #{i+1}: missing 'title'")
            skipped += 1
            continue

        # Resolve assignee
        assignee_id = None
        assignee_name = (task.get("assignee") or "").strip()
        if assignee_name:
            user = db.query(User).filter(User.display_name == assignee_name).first()
            if not user:
                user = User(display_name=assignee_name, email=f"{assignee_name.lower().replace(' ', '.')}@imported.local", is_active=True)
                db.add(user)
                db.flush()
            assignee_id = user.id

        # Resolve service
        service_id = None
        service_name = (task.get("service") or "").strip()
        if service_name:
            svc = db.query(Service).filter(Service.name == service_name).first()
            if not svc:
                svc = Service(name=service_name, category="Imported", status="active")
                db.add(svc)
                db.flush()
            service_id = svc.id

        status = (task.get("status") or "Open").strip()
        if status not in ("Open", "Done", "Blocked"):
            status = "Open"

        # Parse dates
        created_at = None
        if task.get("created_at"):
            try:
                created_at = datetime.fromisoformat(task["created_at"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        if not created_at:
            created_at = datetime.now(timezone.utc)

        completed_at = None
        if task.get("completed_at"):
            try:
                completed_at = datetime.fromisoformat(task["completed_at"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        # Check for duplicate (same title + assignee + created_at day)
        title_match = db.query(WorkItem).filter(
            WorkItem.title == title,
            WorkItem.assignee_id == assignee_id,
        ).first()
        if title_match:
            errors.append(f"Task #{i+1}: '{title[:40]}' already exists — skipped")
            skipped += 1
            continue

        item = WorkItem(
            title=title,
            description=task.get("description"),
            service_id=service_id,
            work_type=task.get("work_type", "Other"),
            source="Manual",
            source_url=task.get("source_url"),
            source_id=task.get("source_id"),
            requester_name=task.get("requester"),
            requester_email=task.get("requester_email"),
            assignee_id=assignee_id,
            status=status,
            estimate_hours=task.get("estimate_hours"),
            actual_hours=task.get("actual_hours"),
            blocked_reason=task.get("blocked_reason"),
            created_at=created_at,
            completed_at=completed_at,
        )
        db.add(item)
        imported += 1

    db.commit()

    return TemplateResponse("import.html", {
        "request": request,
        "result": {
            "success": imported > 0,
            "error": None,
            "imported": imported,
            "skipped": skipped,
            "total": len(tasks),
            "errors": errors[:20],
            "filename": file.filename,
        },
    })
