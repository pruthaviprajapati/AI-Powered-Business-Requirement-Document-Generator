"""
Meeting service – all business logic for meeting CRUD.
Phase 2 will add audio upload, transcription and ML processing here.
"""
from typing import List

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.meeting import Meeting
from app.models.project import Project
from app.schemas.meeting_schema import MeetingCreate, MeetingUpdate


class MeetingService:

    # ── Ownership guard ───────────────────────────────────────────

    @staticmethod
    def _assert_project_ownership(db: Session, project_id: int, owner_id: int) -> Project:
        """Raise 404 if the project doesn't belong to owner_id."""
        project = (
            db.query(Project)
            .filter(
                Project.id == project_id,
                Project.owner_id == owner_id,
                Project.is_active == True,
            )
            .first()
        )
        if not project:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project not found.",
            )
        return project

    # ── Create ────────────────────────────────────────────────────

    @staticmethod
    def create(db: Session, payload: MeetingCreate, owner_id: int) -> Meeting:
        # Verify the user owns the target project
        MeetingService._assert_project_ownership(db, payload.project_id, owner_id)

        meeting = Meeting(
            title=payload.title,
            description=payload.description,
            meeting_date=payload.meeting_date,
            duration_minutes=payload.duration_minutes,
            participants=payload.participants,
            project_id=payload.project_id,
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return meeting

    # ── Read ──────────────────────────────────────────────────────

    @staticmethod
    def get_by_id(db: Session, meeting_id: int, owner_id: int) -> Meeting:
        """Fetch meeting scoped to the current user via project ownership."""
        meeting = (
            db.query(Meeting)
            .join(Project, Meeting.project_id == Project.id)
            .filter(
                Meeting.id == meeting_id,
                Meeting.is_active == True,
                Project.owner_id == owner_id,
                Project.is_active == True,
            )
            .first()
        )
        if not meeting:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Meeting not found.",
            )
        return meeting

    @staticmethod
    def get_all(db: Session, owner_id: int, project_id: int = None) -> List[Meeting]:
        """Return all meetings for the user, optionally filtered by project."""
        query = (
            db.query(Meeting)
            .join(Project, Meeting.project_id == Project.id)
            .filter(
                Meeting.is_active == True,
                Project.owner_id == owner_id,
                Project.is_active == True,
            )
        )
        if project_id:
            query = query.filter(Meeting.project_id == project_id)
        return query.order_by(Meeting.created_at.desc()).all()

    # ── Update ────────────────────────────────────────────────────

    @staticmethod
    def update(db: Session, meeting_id: int, payload: MeetingUpdate, owner_id: int) -> Meeting:
        meeting = MeetingService.get_by_id(db, meeting_id, owner_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(meeting, field, value)
        db.commit()
        db.refresh(meeting)
        return meeting

    # ── Delete ────────────────────────────────────────────────────

    @staticmethod
    def delete(db: Session, meeting_id: int, owner_id: int) -> None:
        """Soft-delete a meeting."""
        meeting = MeetingService.get_by_id(db, meeting_id, owner_id)
        meeting.is_active = False
        db.commit()
