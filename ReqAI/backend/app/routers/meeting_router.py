"""
Meeting router – full CRUD for meetings.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.common_schema import SuccessResponse
from app.schemas.meeting_schema import (
    MeetingCreate,
    MeetingListResponse,
    MeetingResponse,
    MeetingUpdate,
)
from app.services.meeting_service import MeetingService

router = APIRouter(prefix="/meetings", tags=["Meetings"])


@router.post("/", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(
    payload: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new meeting inside a project."""
    meeting = MeetingService.create(db, payload, current_user.id)
    return MeetingResponse.model_validate(meeting)


@router.get("/", response_model=MeetingListResponse)
def list_meetings(
    project_id: Optional[int] = Query(default=None, description="Filter by project ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all meetings for the user, optionally filtered by project."""
    meetings = MeetingService.get_all(db, current_user.id, project_id)
    return MeetingListResponse(
        total=len(meetings),
        meetings=[MeetingResponse.model_validate(m) for m in meetings],
    )


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single meeting by ID."""
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)
    return MeetingResponse.model_validate(meeting)


@router.put("/{meeting_id}", response_model=MeetingResponse)
def update_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update meeting details."""
    meeting = MeetingService.update(db, meeting_id, payload, current_user.id)
    return MeetingResponse.model_validate(meeting)


@router.delete("/{meeting_id}", response_model=SuccessResponse)
def delete_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a meeting."""
    MeetingService.delete(db, meeting_id, current_user.id)
    return SuccessResponse(message="Meeting deleted successfully.")
