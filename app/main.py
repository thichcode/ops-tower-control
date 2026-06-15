from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.config import SESSION_SECRET
from app.database import engine, Base
from app import models  # noqa: F401  ensure all models are registered before create_all

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Ops Control Tower")
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

from app.routers import work_items, services, users, intake, dashboards, capacity, requester, retention, performance, importer, reviews, auth as auth_router

app.include_router(work_items.router)
app.include_router(services.router)
app.include_router(users.router)
app.include_router(intake.router)
app.include_router(dashboards.router)
app.include_router(capacity.router)
app.include_router(requester.router)
app.include_router(retention.router)
app.include_router(performance.router)
app.include_router(importer.router)
app.include_router(reviews.router)
app.include_router(auth_router.router)
