"""
Project router – full CRUD for projects.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.db import get_db
from app.models.user import User
from app.schemas.common_schema import SuccessResponse
from app.schemas.project_schema import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new project for the authenticated user."""
    project = ProjectService.create(db, payload, current_user)
    response = ProjectResponse.model_validate(project)
    response.meeting_count = ProjectService.get_meeting_count(db, project.id)
    return response


@router.get("/", response_model=ProjectListResponse)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List all projects owned by the authenticated user."""
    projects = ProjectService.get_all(db, current_user.id)
    project_responses = []
    for p in projects:
        pr = ProjectResponse.model_validate(p)
        pr.meeting_count = ProjectService.get_meeting_count(db, p.id)
        project_responses.append(pr)
    return ProjectListResponse(total=len(project_responses), projects=project_responses)


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single project by ID."""
    project = ProjectService.get_by_id(db, project_id, current_user.id)
    response = ProjectResponse.model_validate(project)
    response.meeting_count = ProjectService.get_meeting_count(db, project.id)
    return response


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update a project."""
    project = ProjectService.update(db, project_id, payload, current_user.id)
    response = ProjectResponse.model_validate(project)
    response.meeting_count = ProjectService.get_meeting_count(db, project.id)
    return response


@router.delete("/{project_id}", response_model=SuccessResponse)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a project."""
    ProjectService.delete(db, project_id, current_user.id)
    return SuccessResponse(message="Project deleted successfully.")
