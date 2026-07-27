"""
Project service – all business logic for project CRUD.
"""
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.user import User
from app.schemas.project_schema import ProjectCreate, ProjectUpdate


class ProjectService:

    # ── Create ────────────────────────────────────────────────────

    @staticmethod
    def create(db: Session, payload: ProjectCreate, owner: User) -> Project:
        project = Project(
            name=payload.name,
            description=payload.description,
            client_name=payload.client_name,
            client_email=payload.client_email,
            owner_id=owner.id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    # ── Read ──────────────────────────────────────────────────────

    @staticmethod
    def get_by_id(db: Session, project_id: int, owner_id: int) -> Project:
        """Fetch a project by ID, scoped to the current user."""
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

    @staticmethod
    def get_all(db: Session, owner_id: int) -> List[Project]:
        """Return all active projects owned by the user."""
        return (
            db.query(Project)
            .filter(Project.owner_id == owner_id, Project.is_active == True)
            .order_by(Project.created_at.desc())
            .all()
        )

    # ── Update ────────────────────────────────────────────────────

    @staticmethod
    def update(db: Session, project_id: int, payload: ProjectUpdate, owner_id: int) -> Project:
        project = ProjectService.get_by_id(db, project_id, owner_id)
        update_data = payload.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(project, field, value)
        db.commit()
        db.refresh(project)
        return project

    # ── Delete ────────────────────────────────────────────────────

    @staticmethod
    def delete(db: Session, project_id: int, owner_id: int) -> None:
        """Soft-delete a project."""
        project = ProjectService.get_by_id(db, project_id, owner_id)
        project.is_active = False
        db.commit()

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def get_meeting_count(db: Session, project_id: int) -> int:
        from app.models.meeting import Meeting
        return (
            db.query(Meeting)
            .filter(Meeting.project_id == project_id, Meeting.is_active == True)
            .count()
        )
