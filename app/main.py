from fastapi import FastAPI

from app.database import engine, Base
from app import models  # noqa: F401  ensure all models are registered before create_all

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ops Control Tower")

from app.routers import work_items, services, users, intake, dashboards, capacity, requester, retention, performance

app.include_router(work_items.router)
app.include_router(services.router)
app.include_router(users.router)
app.include_router(intake.router)
app.include_router(dashboards.router)
app.include_router(capacity.router)
app.include_router(requester.router)
app.include_router(retention.router)
app.include_router(performance.router)
