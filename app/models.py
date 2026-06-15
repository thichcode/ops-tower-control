from sqlalchemy import Column, Integer, Text, Numeric, Boolean, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    display_name = Column(Text, nullable=False)
    email = Column(Text, unique=True, nullable=False)
    password_hash = Column(Text, nullable=True)
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
    requester_token = Column(Text, nullable=True, unique=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    service = relationship("Service")
    assignee = relationship("User")


class AIReview(Base):
    __tablename__ = "ai_reviews"

    id = Column(Integer, primary_key=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False)
    state = Column(Text, nullable=False, default="pending")
    provider = Column(Text, nullable=False, default="rules")
    model = Column(Text, nullable=True)
    evidence = Column(JSON, nullable=False)
    suggestion = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    reviewed_at = Column(DateTime, nullable=True)

    work_item = relationship("WorkItem")


class WorkItemEvidence(Base):
    __tablename__ = "work_item_evidence"

    id = Column(Integer, primary_key=True)
    work_item_id = Column(Integer, ForeignKey("work_items.id"), nullable=False)
    source = Column(Text, nullable=False)
    source_message_id = Column(Text, nullable=True)
    thread_id = Column(Text, nullable=True)
    sender_name = Column(Text, nullable=True)
    body_excerpt = Column(Text, nullable=True)
    event_type = Column(Text, nullable=False, default="message")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    work_item = relationship("WorkItem")


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


class RetentionScore(Base):
    __tablename__ = "retention_scores"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(Text, nullable=False)
    risk_level = Column(Text, nullable=False, default="Low")
    flag_count = Column(Integer, default=0)
    signals = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
