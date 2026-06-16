from fastapi import APIRouter, Depends, Request, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from html.parser import HTMLParser
import re
import json
import os
import secrets

from app.auth import role_required
from app.database import get_db
from app.models import User, Service, WorkItem
from app.services.member_intake import import_member_package
from app.templates import TemplateResponse

router = APIRouter(prefix="/import", tags=["import"])

KNOWN_SERVICES = ["Kubernetes", "Cloudflare", "Backup", "Zabbix", "ServiceDesk", "GitLab", "SharePoint", "VPN", "SVN"]

DONE_KEYWORDS = {"done", "completed", "hoàn thành", "xong", "đã xong", "resolved", "đã resolve", "closed", "đã đóng"}
BLOCKED_KEYWORDS = {"blocked", "halted", "stalled", "tạm dừng", "vướng", "chờ", "waiting", "pending"}
OPEN_KEYWORDS = {"open", "in progress", "đang làm", "đang xử lý", "started", "bắt đầu"}

# Convention tags: [DONE], [BLOCKED], [OPEN] at end of message
STATUS_TAG_RE = re.compile(r"\[(DONE|XONG|HOÀN THÀNH|BLOCKED|TẠM DỪNG|VƯỚNG|OPEN|ĐANG LÀM)\]\s*$", re.IGNORECASE)
STATUS_TAG_MAP = {
    "DONE": "Done", "XONG": "Done", "HOÀN THÀNH": "Done",
    "BLOCKED": "Blocked", "TẠM DỪNG": "Blocked", "VƯỚNG": "Blocked",
    "OPEN": "Open", "ĐANG LÀM": "Open",
}


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts = []

    def handle_data(self, data):
        self._parts.append(data)

    def get_text(self):
        return "".join(self._parts).strip()


def strip_html(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def detect_service(text: str) -> str:
    text_lower = text.lower()
    for svc in KNOWN_SERVICES:
        if svc.lower() in text_lower:
            return svc
    return ""


def detect_status(text: str) -> str:
    """Detect status: first check convention tag [DONE]/[BLOCKED]/[OPEN], then keyword fallback."""
    # Priority 1: convention tag at end of message
    tag_match = STATUS_TAG_RE.search(text)
    if tag_match:
        tag = tag_match.group(1).upper()
        return STATUS_TAG_MAP.get(tag, "Open")

    # Priority 2: keyword detection (fallback)
    text_lower = text.lower()
    for kw in DONE_KEYWORDS:
        if kw in text_lower:
            return "Done"
    for kw in BLOCKED_KEYWORDS:
        if kw in text_lower:
            return "Blocked"
    return "Open"


def extract_title_from_message(msg: dict) -> str:
    subject = (msg.get("subject") or "").strip()
    if subject:
        return STATUS_TAG_RE.sub("", subject).strip()[:120]

    body = msg.get("body", {})
    if isinstance(body, dict):
        content = body.get("content", "")
    else:
        content = str(body)

    text = strip_html(content) if "<" in content else content
    first_line = text.split("\n")[0].strip()
    first_line = STATUS_TAG_RE.sub("", first_line).strip()
    return first_line[:120] if first_line else "(no subject)"


def parse_pa_message(msg: dict) -> dict:
    """Parse a single Power Automate Teams message into a task dict."""
    # Extract assignee
    from_data = msg.get("from", {})
    user_data = from_data.get("user", from_data)
    assignee = user_data.get("displayName", "")

    # Extract body content
    body = msg.get("body", {})
    if isinstance(body, dict):
        content = body.get("content", "")
        content_type = body.get("contentType", "text")
    else:
        content = str(body)
        content_type = "html" if "<" in content else "text"

    text = strip_html(content) if content_type == "html" or "<" in content else content

    # Title = subject or first line (strip status tag)
    title = extract_title_from_message(msg)

    # Clean description: strip tags from full text
    clean_text = STATUS_TAG_RE.sub("", text).strip()

    # Detect service and status from full text
    service = detect_service(text)
    status = detect_status(text)

    # Parse date
    created_at = msg.get("createdDateTime", "")

    # Message ID for dedup
    message_id = msg.get("id", msg.get("messageId", ""))

    # Channel info
    channel_id = msg.get("channelId", "")
    conversation_id = msg.get("conversationId", "")

    return {
        "title": title,
        "description": clean_text if clean_text != title else "",
        "service": service,
        "assignee": assignee,
        "status": status,
        "created_at": created_at,
        "source_id": message_id,
        "source_url": f"https://teams.microsoft.com/l/message/{channel_id}/{message_id}" if channel_id and message_id else "",
    }


def parse_file(data: dict) -> list:
    """Detect format and return list of task dicts."""
    # Format 1: Simple tasks[] — manual format
    if "tasks" in data and isinstance(data["tasks"], list):
        return data["tasks"]

    # Format 2: Power Automate "value" array (Get messages action)
    if "value" in data and isinstance(data["value"], list):
        return [parse_pa_message(msg) for msg in data["value"]]

    # Format 3: Power Automate "messages" array (custom flow)
    if "messages" in data and isinstance(data["messages"], list):
        return [parse_pa_message(msg) for msg in data["messages"]]

    # Format 4: Single message (not array)
    if "body" in data and ("from" in data or "createdDateTime" in data):
        return [parse_pa_message(data)]

    return []


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
    _=Depends(role_required("leader", "admin")),
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

    tasks = parse_file(data)
    if data.get("schema_version") and isinstance(data.get("items"), list):
        result = import_member_package(db, data)
        result["filename"] = file.filename
        result["error"] = None
        return TemplateResponse("import.html", {
            "request": request,
            "result": result,
        })

    if not tasks:
        return TemplateResponse("import.html", {
            "request": request,
            "result": {"success": False, "error": "No tasks found. Expected: 'tasks[]', 'value[]' (PA format), or 'messages[]'", "imported": 0, "skipped": 0, "errors": []},
        })

    imported = 0
    skipped = 0
    errors = []

    for i, task in enumerate(tasks):
        title = (task.get("title") or "").strip()
        if not title or title == "(no subject)":
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
        elif status == "Done":
            completed_at = datetime.now(timezone.utc)

        # Duplicate detection: same title + assignee OR same source_id
        source_id = (task.get("source_id") or "").strip()
        existing = None
        if source_id:
            existing = db.query(WorkItem).filter(WorkItem.source_id == source_id).first()
        if not existing:
            existing = db.query(WorkItem).filter(
                WorkItem.title == title,
                WorkItem.assignee_id == assignee_id,
            ).first()
        if existing:
            errors.append(f"Task #{i+1}: '{title[:40]}' already exists — skipped")
            skipped += 1
            continue

        item = WorkItem(
            title=title,
            description=task.get("description"),
            service_id=service_id,
            work_type=task.get("work_type", "Other"),
            source="Teams",
            source_url=task.get("source_url"),
            source_id=source_id or None,
            requester_name=task.get("requester"),
            requester_email=task.get("requester_email"),
            assignee_id=assignee_id,
            status=status,
            estimate_hours=task.get("estimate_hours"),
            actual_hours=task.get("actual_hours"),
            blocked_reason=task.get("blocked_reason"),
            requester_token=secrets.token_urlsafe(16),
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
