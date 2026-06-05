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
    source_url = Column(Text, nullable=True)
    source_id = Column(Text, nullable=True)
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


class Capacity(Base):
    __tablename__ = "capacity"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(Text, nullable=False)
    capacity_hours = Column(Numeric(10, 2), nullable=False)
    leave_hours = Column(Numeric(10, 2), default=0)
    meeting_hours = Column(Numeric(10, 2), default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
