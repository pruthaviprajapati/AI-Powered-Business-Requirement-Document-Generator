"""
Pydantic schemas for Project request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


# ── Create ────────────────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_email: Optional[EmailStr] = None


# ── Update ────────────────────────────────────────────────────────────────────

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_email: Optional[EmailStr] = None
    status: Optional[str] = None


# ── Response ──────────────────────────────────────────────────────────────────

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    client_name: Optional[str] = None
    client_email: Optional[str] = None
    status: str
    owner_id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    meeting_count: Optional[int] = 0

    model_config = {"from_attributes": True}


class ProjectListResponse(BaseModel):
    total: int
    projects: list[ProjectResponse]
