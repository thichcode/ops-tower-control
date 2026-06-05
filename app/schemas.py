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
