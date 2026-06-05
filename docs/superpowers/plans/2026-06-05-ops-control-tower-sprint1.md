# Ops Control Tower Sprint 1 — Implementation Plan

> **Goal:** Core data + manual work capture with FastAPI, PostgreSQL, Jinja2 templates.

**Architecture:** Server-rendered HTML with FastAPI. No auth. No async workers. Bootstrap 5 UI with vanilla JS for 1-click actions.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Jinja2, Bootstrap 5

---

### Task 1: Project Setup — Config, Database, Models

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/config.py`
- Create: `app/database.py`
- Create: `app/models.py`

- [ ] **Create requirements.txt**

```
fastapi==0.115.6
uvicorn==0.34.0
sqlalchemy==2.0.36
alembic==1.14.0
psycopg2-binary==2.9.10
jinja2==3.1.4
python-multipart==0.0.19
```

- [ ] **Create app/__init__.py** — empty

- [ ] **Create app/config.py**
```python
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/opsdash")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
```

- [ ] **Create app/database.py**
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Create app/models.py**
```python
from sqlalchemy import Column, Integer, Text, Numeric, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    display_name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    role = Column(Text, default="member")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True)
    name = Column(Text, unique=True, nullable=False)
    category = Column(Text, nullable=True)
    status = Column(Text, default="active")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(Integer, primary_key=True)
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=True)
    work_type = Column(Text, default="Other")
    source = Column(Text, default="Manual")
    requester_name = Column(Text, nullable=True)
    requester_email = Column(Text, nullable=True)
    assignee_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Text, default="Open")
    estimate_hours = Column(Numeric(10, 2), nullable=True)
    actual_hours = Column(Numeric(10, 2), nullable=True)
    blocked_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    service = relationship("Service")
    assignee = relationship("User")
```

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: project setup with config, database, models"
```

---

### Task 2: Pydantic Schemas

**Files:**
- Create: `app/schemas.py`

- [ ] **Create app/schemas.py**
```python
from pydantic import BaseModel
from typing import Optional
from decimal import Decimal


class WorkItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    service_id: Optional[int] = None
    work_type: Optional[str] = "Other"
    source: Optional[str] = "Manual"
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    assignee_id: Optional[int] = None
    estimate_hours: Optional[Decimal] = None


class WorkItemUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    service_id: Optional[int] = None
    work_type: Optional[str] = None
    requester_name: Optional[str] = None
    requester_email: Optional[str] = None
    assignee_id: Optional[int] = None
    estimate_hours: Optional[Decimal] = None
    notes: Optional[str] = None


class ServiceCreate(BaseModel):
    name: str
    category: Optional[str] = None


class UserCreate(BaseModel):
    display_name: str
    email: str
    role: Optional[str] = "member"
```

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: add pydantic schemas"
```

---

### Task 3: Main App + Router Scaffold

**Files:**
- Create: `app/main.py`
- Create: `app/routers/__init__.py`

- [ ] **Create app/main.py**
```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ops Control Tower")

from app.routers import work_items, services, users

app.include_router(work_items.router)
app.include_router(services.router)
app.include_router(users.router)
```

- [ ] **Create app/routers/__init__.py** — empty

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: main app entry point"
```

---

### Task 4: Templates — base.html + my_work.html

**Files:**
- Create: `app/templates/base.html`
- Create: `app/templates/my_work.html`

- [ ] **Create app/templates/base.html**
```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Ops Control Tower{% endblock %}</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
  <nav class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
    <div class="container">
      <a class="navbar-brand" href="/">Ops Control Tower</a>
      <div class="collapse navbar-collapse">
        <ul class="navbar-nav ms-auto">
          <li class="nav-item"><a class="nav-link" href="/">My Work</a></li>
          <li class="nav-item"><a class="nav-link" href="/services">Services</a></li>
          <li class="nav-item"><a class="nav-link" href="/users">Users</a></li>
        </ul>
      </div>
    </div>
  </nav>

  <div class="container">
    {% block content %}{% endblock %}
  </div>

  <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
```

- [ ] **Create app/templates/my_work.html**
```html
{% extends "base.html" %}
{% block title %}My Work{% endblock %}
{% block content %}

<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>My Work</h2>
  <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addModal">+ Quick Add</button>
</div>

<form method="GET" class="row g-2 mb-3">
  <div class="col-auto">
    <select name="status" class="form-select" onchange="this.form.submit()">
      <option value="">All Status</option>
      <option value="Open" {{ 'selected' if request.query_params.get('status') == 'Open' }}>Open</option>
      <option value="Done" {{ 'selected' if request.query_params.get('status') == 'Done' }}>Done</option>
      <option value="Blocked" {{ 'selected' if request.query_params.get('status') == 'Blocked' }}>Blocked</option>
      <option value="Cancelled" {{ 'selected' if request.query_params.get('status') == 'Cancelled' }}>Cancelled</option>
    </select>
  </div>
  <div class="col-auto">
    <select name="assignee_id" class="form-select" onchange="this.form.submit()">
      <option value="">All Members</option>
      {% for u in users %}
      <option value="{{ u.id }}" {{ 'selected' if request.query_params.get('assignee_id')|string == u.id|string }}>{{ u.display_name }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-auto">
    <input type="text" name="q" class="form-control" placeholder="Search..." value="{{ request.query_params.get('q', '') }}">
  </div>
  <div class="col-auto">
    <button class="btn btn-outline-secondary" type="submit">Filter</button>
  </div>
</form>

<div class="table-responsive">
  <table class="table table-hover align-middle">
    <thead class="table-dark">
      <tr>
        <th>Title</th>
        <th>Requester</th>
        <th>Service</th>
        <th>Source</th>
        <th>Age</th>
        <th>Status</th>
        <th>Actions</th>
      </tr>
    </thead>
    <tbody>
      {% for item in work_items %}
      <tr>
        <td>
          <a href="/work-items/{{ item.id }}/edit" class="text-decoration-none">{{ item.title }}</a>
        </td>
        <td>{{ item.requester_name or '-' }}</td>
        <td>{{ item.service.name if item.service else '-' }}</td>
        <td>{{ item.source }}</td>
        <td class="{{ 'text-warning' if item.age_days > 3 and item.age_days <= 7 else 'text-danger' if item.age_days > 7 }}">
          {{ item.age_days }}d
        </td>
        <td>
          {% if item.status == 'Open' %}
            <span class="badge bg-primary">Open</span>
          {% elif item.status == 'Done' %}
            <span class="badge bg-success">Done</span>
          {% elif item.status == 'Blocked' %}
            <span class="badge bg-warning text-dark">Blocked</span>
          {% else %}
            <span class="badge bg-secondary">{{ item.status }}</span>
          {% endif %}
        </td>
        <td>
          {% if item.status == 'Open' or item.status == 'Blocked' %}
          <form method="POST" action="/work-items/{{ item.id }}/done" style="display:inline">
            <button class="btn btn-sm btn-success" title="Done">✓</button>
          </form>
          {% endif %}
          {% if item.status == 'Open' %}
          <form method="POST" action="/work-items/{{ item.id }}/blocked" style="display:inline" onsubmit="return prompt('Block reason:') ? true : false">
            <input type="hidden" name="reason" id="reason-{{ item.id }}" value="">
            <button class="btn btn-sm btn-warning" title="Blocked">⊘</button>
          </form>
          {% endif %}
        </td>
      </tr>
      {% else %}
      <tr><td colspan="7" class="text-center text-muted">No work items found</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<!-- Quick Add Modal -->
<div class="modal fade" id="addModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <form method="POST" action="/work-items">
        <div class="modal-header"><h5>Quick Add Task</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label">Title *</label>
            <input type="text" name="title" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label">Service</label>
            <select name="service_id" class="form-select">
              <option value="">-- None --</option>
              {% for s in services %}
              <option value="{{ s.id }}">{{ s.name }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Work Type</label>
            <select name="work_type" class="form-select">
              {% for wt in ['Incident', 'Request', 'Project', 'Audit', 'Consulting', 'Improvement', 'PoC', 'Meeting', 'Training', 'Vendor', 'Risk', 'Other'] %}
              <option value="{{ wt }}">{{ wt }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Requester Name</label>
            <input type="text" name="requester_name" class="form-control">
          </div>
          <div class="mb-3">
            <label class="form-label">Assignee</label>
            <select name="assignee_id" class="form-select">
              <option value="">-- Unassigned --</option>
              {% for u in users %}
              <option value="{{ u.id }}">{{ u.display_name }}</option>
              {% endfor %}
            </select>
          </div>
          <div class="mb-3">
            <label class="form-label">Estimate Hours</label>
            <input type="number" step="0.5" name="estimate_hours" class="form-control">
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn btn-primary" type="submit">Add Task</button>
        </div>
      </form>
    </div>
  </div>
</div>

<script>
document.getElementById('addModal').addEventListener('hidden.bs.modal', function () {
  this.querySelector('form').reset();
});
</script>

{% endblock %}
```

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: base layout and my work template"
```

---

### Task 5: Work Items Router

**Files:**
- Create: `app/routers/work_items.py`
- Create: `app/templates/work_item_form.html`

- [ ] **Create app/routers/work_items.py**
```python
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from app.database import get_db
from app.models import WorkItem, User, Service
from app.schemas import WorkItemCreate, WorkItemUpdate

router = APIRouter()


@router.get("/")
def my_work(
    request: Request,
    status: Optional[str] = None,
    assignee_id: Optional[int] = None,
    q: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(WorkItem)
    if status:
        query = query.filter(WorkItem.status == status)
    if assignee_id:
        query = query.filter(WorkItem.assignee_id == assignee_id)
    if q:
        query = query.filter(WorkItem.title.ilike(f"%{q}%"))
    work_items = query.order_by(WorkItem.created_at.desc()).all()

    now = datetime.now(timezone.utc)
    for item in work_items:
        created = item.created_at.replace(tzinfo=timezone.utc) if item.created_at.tzinfo is None else item.created_at
        item.age_days = (now - created).days

    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()
    services = db.query(Service).filter(Service.status == "active").order_by(Service.name).all()

    return TemplateResponse("my_work.html", {
        "request": request,
        "work_items": work_items,
        "users": users,
        "services": services,
    })


@router.post("/work-items")
def create_work_item(
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    service_id: Optional[int] = Form(None),
    work_type: Optional[str] = Form("Other"),
    requester_name: Optional[str] = Form(None),
    assignee_id: Optional[int] = Form(None),
    estimate_hours: Optional[Decimal] = Form(None),
    db: Session = Depends(get_db),
):
    item = WorkItem(
        title=title,
        description=description,
        service_id=service_id,
        work_type=work_type,
        requester_name=requester_name,
        assignee_id=assignee_id,
        estimate_hours=estimate_hours,
    )
    db.add(item)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/work-items/{item_id}/done")
def done_work_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.status = "Done"
        item.completed_at = datetime.now(timezone.utc)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.post("/work-items/{item_id}/blocked")
def block_work_item(item_id: int, reason: Optional[str] = Form(None), db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.status = "Blocked"
        item.blocked_reason = reason
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@router.get("/work-items/{item_id}/edit")
def edit_work_item(request: Request, item_id: int, db: Session = Depends(get_db)):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    users = db.query(User).filter(User.is_active == True).order_by(User.display_name).all()
    services = db.query(Service).order_by(Service.name).all()
    return TemplateResponse("work_item_form.html", {
        "request": request,
        "item": item,
        "users": users,
        "services": services,
    })


@router.post("/work-items/{item_id}/edit")
def update_work_item(
    item_id: int,
    title: str = Form(...),
    description: Optional[str] = Form(None),
    service_id: Optional[int] = Form(None),
    work_type: Optional[str] = Form(None),
    requester_name: Optional[str] = Form(None),
    assignee_id: Optional[int] = Form(None),
    estimate_hours: Optional[Decimal] = Form(None),
    notes: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    item = db.query(WorkItem).filter(WorkItem.id == item_id).first()
    if item:
        item.title = title
        item.description = description
        item.service_id = service_id
        item.work_type = work_type
        item.requester_name = requester_name
        item.assignee_id = assignee_id
        item.estimate_hours = estimate_hours
        item.notes = notes
        db.commit()
    return RedirectResponse(url="/", status_code=303)
```

Need to add the import for TemplateResponse — update to include it:

```python
from fastapi.templating import Jinja2Templates
from app.config import TEMPLATES_DIR

templates = Jinja2Templates(directory=TEMPLATES_DIR)
TemplateResponse = templates.TemplateResponse
```

- [ ] **Create app/templates/work_item_form.html**
```html
{% extends "base.html" %}
{% block title %}Edit Task{% endblock %}
{% block content %}

<h2>Edit Task</h2>
<form method="POST" class="row g-3" style="max-width: 600px;">
  <div class="col-12">
    <label class="form-label">Title *</label>
    <input type="text" name="title" class="form-control" value="{{ item.title }}" required>
  </div>
  <div class="col-12">
    <label class="form-label">Description</label>
    <textarea name="description" class="form-control" rows="3">{{ item.description or '' }}</textarea>
  </div>
  <div class="col-6">
    <label class="form-label">Service</label>
    <select name="service_id" class="form-select">
      <option value="">-- None --</option>
      {% for s in services %}
      <option value="{{ s.id }}" {{ 'selected' if item.service_id == s.id }}>{{ s.name }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-6">
    <label class="form-label">Work Type</label>
    <select name="work_type" class="form-select">
      {% for wt in ['Incident', 'Request', 'Project', 'Audit', 'Consulting', 'Improvement', 'PoC', 'Meeting', 'Training', 'Vendor', 'Risk', 'Other'] %}
      <option value="{{ wt }}" {{ 'selected' if item.work_type == wt }}>{{ wt }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-6">
    <label class="form-label">Requester Name</label>
    <input type="text" name="requester_name" class="form-control" value="{{ item.requester_name or '' }}">
  </div>
  <div class="col-6">
    <label class="form-label">Assignee</label>
    <select name="assignee_id" class="form-select">
      <option value="">-- Unassigned --</option>
      {% for u in users %}
      <option value="{{ u.id }}" {{ 'selected' if item.assignee_id == u.id }}>{{ u.display_name }}</option>
      {% endfor %}
    </select>
  </div>
  <div class="col-6">
    <label class="form-label">Estimate Hours</label>
    <input type="number" step="0.5" name="estimate_hours" class="form-control" value="{{ item.estimate_hours or '' }}">
  </div>
  <div class="col-12">
    <label class="form-label">Notes</label>
    <textarea name="notes" class="form-control" rows="2">{{ item.notes or '' }}</textarea>
  </div>
  <div class="col-12">
    <button class="btn btn-primary" type="submit">Save</button>
    <a href="/" class="btn btn-outline-secondary">Cancel</a>
  </div>
</form>

{% endblock %}
```

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: work items CRUD with templates"
```

---

### Task 6: Services Router

**Files:**
- Create: `app/routers/services.py`
- Create: `app/templates/services.html`

- [ ] **Create app/routers/services.py**
```python
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Service
from app.schemas import ServiceCreate

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
```

- [ ] **Create app/templates/services.html**
```html
{% extends "base.html" %}
{% block title %}Services{% endblock %}
{% block content %}

<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>Service Catalog</h2>
  <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addModal">+ Add Service</button>
</div>

<table class="table table-hover">
  <thead class="table-dark">
    <tr><th>Name</th><th>Category</th><th>Status</th><th>Actions</th></tr>
  </thead>
  <tbody>
    {% for s in services %}
    <tr>
      <td>{{ s.name }}</td>
      <td>{{ s.category or '-' }}</td>
      <td>{{ s.status }}</td>
      <td>
        <form method="POST" action="/services/{{ s.id }}/delete" onsubmit="return confirm('Delete {{ s.name }}?')">
          <button class="btn btn-sm btn-danger">Delete</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="4" class="text-center text-muted">No services</td></tr>
    {% endfor %}
  </tbody>
</table>

<div class="modal fade" id="addModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <form method="POST" action="/services">
        <div class="modal-header"><h5>Add Service</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label">Name *</label>
            <input type="text" name="name" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label">Category</label>
            <select name="category" class="form-select">
              <option value="">-- None --</option>
              {% for cat in ['Enterprise Applications', 'DevOps Platform', 'Observability', 'Collaboration', 'Cloud & Edge', 'Business Continuity', 'Other'] %}
              <option value="{{ cat }}">{{ cat }}</option>
              {% endfor %}
            </select>
          </div>
        </div>
        <div class="modal-footer"><button class="btn btn-primary" type="submit">Add</button></div>
      </form>
    </div>
  </div>
</div>

{% endblock %}
```

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: service catalog CRUD"
```

---

### Task 7: Users Router

**Files:**
- Create: `app/routers/users.py`
- Create: `app/templates/users.html`

- [ ] **Create app/routers/users.py**
```python
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserCreate

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
```

- [ ] **Create app/templates/users.html**
```html
{% extends "base.html" %}
{% block title %}Users{% endblock %}
{% block content %}

<div class="d-flex justify-content-between align-items-center mb-3">
  <h2>User Management</h2>
  <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#addModal">+ Add User</button>
</div>

<table class="table table-hover">
  <thead class="table-dark">
    <tr><th>Name</th><th>Email</th><th>Role</th><th>Active</th><th>Actions</th></tr>
  </thead>
  <tbody>
    {% for u in users %}
    <tr>
      <td>{{ u.display_name }}</td>
      <td>{{ u.email }}</td>
      <td>{{ u.role }}</td>
      <td>{{ 'Yes' if u.is_active else 'No' }}</td>
      <td>
        <form method="POST" action="/users/{{ u.id }}/delete" onsubmit="return confirm('Delete {{ u.display_name }}?')">
          <button class="btn btn-sm btn-danger">Delete</button>
        </form>
      </td>
    </tr>
    {% else %}
    <tr><td colspan="5" class="text-center text-muted">No users</td></tr>
    {% endfor %}
  </tbody>
</table>

<div class="modal fade" id="addModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <form method="POST" action="/users">
        <div class="modal-header"><h5>Add User</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
        <div class="modal-body">
          <div class="mb-3">
            <label class="form-label">Display Name *</label>
            <input type="text" name="display_name" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label">Email *</label>
            <input type="email" name="email" class="form-control" required>
          </div>
          <div class="mb-3">
            <label class="form-label">Role</label>
            <select name="role" class="form-select">
              <option value="member">Member</option>
              <option value="leader">Leader</option>
              <option value="admin">Admin</option>
            </select>
          </div>
        </div>
        <div class="modal-footer"><button class="btn btn-primary" type="submit">Add</button></div>
      </form>
    </div>
  </div>
</div>

{% endblock %}
```

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: user management CRUD"
```

---

### Task 8: Seed Data Script

**Files:**
- Create: `seed.py`

- [ ] **Create seed.py**
```python
from app.database import SessionLocal, engine, Base
from app.models import User, Service, WorkItem
from datetime import datetime, timezone, timedelta

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    users = [
        User(display_name="Engineer A", email="eng.a@company.com", role="member"),
        User(display_name="Engineer B", email="eng.b@company.com", role="member"),
        User(display_name="Engineer C", email="eng.c@company.com", role="member"),
        User(display_name="Lead A", email="lead.a@company.com", role="leader"),
    ]
    db.add_all(users)
    db.flush()

    services = [
        Service(name="GitLab", category="DevOps Platform"),
        Service(name="Cloudflare", category="Cloud & Edge"),
        Service(name="Kubernetes", category="DevOps Platform"),
        Service(name="Backup", category="Business Continuity"),
        Service(name="SVN", category="DevOps Platform"),
        Service(name="Zabbix", category="Observability"),
        Service(name="SharePoint", category="Collaboration"),
    ]
    db.add_all(services)
    db.flush()

    now = datetime.now(timezone.utc)
    items = [
        WorkItem(title="Fix Cloudflare DNS record for project ABC", requester_name="PM A", service_id=services[1].id, work_type="Incident", assignee_id=users[0].id, status="Open", created_at=now - timedelta(days=2)),
        WorkItem(title="Weekly backup restore test", requester_name="BA B", service_id=services[3].id, work_type="Request", assignee_id=users[1].id, status="Blocked", blocked_reason="Waiting for approval", created_at=now - timedelta(days=5)),
        WorkItem(title="Kubernetes node upgrade", requester_name="Manager C", service_id=services[2].id, work_type="Project", assignee_id=users[2].id, status="Done", completed_at=now - timedelta(days=1), created_at=now - timedelta(days=10)),
        WorkItem(title="GitLab CI runner maintenance", requester_name="Security Team", service_id=services[0].id, work_type="Improvement", assignee_id=users[0].id, status="Open", created_at=now - timedelta(days=1)),
        WorkItem(title="Audit Cloudflare WAF rules", requester_name="Audit Team", service_id=services[1].id, work_type="Audit", assignee_id=users[1].id, status="Open", created_at=now - timedelta(days=7)),
        WorkItem(title="SVN to Git migration planning", requester_name="PM A", service_id=services[4].id, work_type="Project", assignee_id=users[2].id, status="Open", created_at=now - timedelta(days=14)),
        WorkItem(title="Zabbix alert tuning for production", requester_name="Manager C", service_id=services[5].id, work_type="Improvement", assignee_id=users[0].id, status="Open", created_at=now - timedelta(days=3)),
        WorkItem(title="SharePoint permissions review", requester_name="BA B", service_id=services[6].id, work_type="Request", assignee_id=users[1].id, status="Open", created_at=now - timedelta(days=4)),
        WorkItem(title="PoC: New monitoring tool evaluation", requester_name="Lead A", work_type="PoC", assignee_id=users[2].id, status="Open", estimate_hours=16, created_at=now - timedelta(days=1)),
        WorkItem(title="Vendor meeting: Cloudflare Enterprise", requester_name="PM A", work_type="Meeting", assignee_id=users[0].id, status="Done", completed_at=now, created_at=now - timedelta(days=2)),
    ]
    db.add_all(items)
    db.commit()
    print("Seed data created successfully!")
    print(f"  Users: {len(users)}")
    print(f"  Services: {len(services)}")
    print(f"  Work Items: {len(items)}")

except Exception as e:
    db.rollback()
    print(f"Error: {e}")
finally:
    db.close()
```

- [ ] **Commit**
```bash
git add -A && git commit -m "feat: seed data script"
```

---

### Task 9: Wire Up TemplateResponse + Fix imports

Need to ensure all routers share the same Jinja2Templates instance.

- [ ] **Update app/routers/__init__.py** — no change needed, empty is fine
- [ ] **Update app/main.py** to initialize templates and make it available

Actually, better approach: create a shared `templates` module. Let me adjust.

Create `app/templates.py`:
```python
from fastapi.templating import Jinja2Templates
from app.config import TEMPLATES_DIR

templates = Jinja2Templates(directory=TEMPLATES_DIR)
```

Then in each router, import and use:
```python
from app.templates import templates
TemplateResponse = templates.TemplateResponse
```

- [ ] **Commit**
```bash
git add -A && git commit -m "fix: shared template renderer"
```

---

### Task 10: Run and Verify

- [ ] **Install dependencies**
```bash
pip install -r requirements.txt
```

- [ ] **Run seed script**
```bash
python seed.py
```
Expected: "Seed data created successfully!"

- [ ] **Start the app**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- [ ] **Verify flows**
1. Open http://localhost:8000 — see My Work with 10 items
2. Test filter by status
3. Test search
4. Click "Quick Add" — create a new task
5. Click "✓" on an Open task — should change to Done
6. Click "⊘" on an Open task — should prompt for reason, change to Blocked
7. Open http://localhost:8000/services — manage services
8. Open http://localhost:8000/users — manage users
9. Click a task title — edit form, save changes

- [ ] **Final commit**
```bash
git add -A && git commit -m "feat: sprint 1 complete"
```
