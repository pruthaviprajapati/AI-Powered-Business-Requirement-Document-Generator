"""
Pydantic schemas for Meeting request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Create ────────────────────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_date: Optional[str] = None
    duration_minutes: Optional[float] = None
    participants: Optional[str] = None
    project_id: int


# ── Update ────────────────────────────────────────────────────────────────────

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    meeting_date: Optional[str] = None
    duration_minutes: Optional[float] = None
    participants: Optional[str] = None
    processing_status: Optional[str] = None


# ── Response ──────────────────────────────────────────────────────────────────

class MeetingResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    meeting_date: Optional[str] = None
    duration_minutes: Optional[float] = None
    participants: Optional[str] = None
    project_id: int
    audio_file: Optional[str] = None
    transcript: Optional[str] = None
    processing_status: str
    generated_brd: Optional[str] = None
    brd_file_path: Optional[str] = None
    requirements_count: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MeetingListResponse(BaseModel):
    total: int
    meetings: list[MeetingResponse]
