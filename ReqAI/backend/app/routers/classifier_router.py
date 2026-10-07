"""
classifier_router.py – API endpoints for Phase 5 DistilBERT classification.

Endpoints:
  POST   /meetings/{id}/classify              – Run DistilBERT on extracted candidates
  GET    /meetings/{id}/classified-requirements – Get classified results
  GET    /models/status                        – Get model training status
"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.classifier.services.distilbert_service import DistilBERTService
from app.auth.dependencies import get_current_user
from app.database.db import get_db
from app.models.meeting import Meeting
from app.models.requirement_candidate import RequirementCandidate
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Phase 5 – ML Classification"])


# ── Response schemas ──────────────────────────────────────────────────────────

class ClassifyResponse(BaseModel):
    success: bool
    meeting_id: int
    classified: int
    total: int
    category_breakdown: dict
    message: str


class ClassifiedRequirementResponse(BaseModel):
    id: int
    meeting_id: int
    speaker: str
    sentence: str
    clean_sentence: str
    category: Optional[str]
    ml_confidence: Optional[float]
    confidence_score: float          # Phase 4 heuristic score
    processing_status: str
    classified_at: Optional[Any]

    model_config = {"from_attributes": True}


class ClassifiedListResponse(BaseModel):
    meeting_id: int
    total: int
    classified_count: int
    category_breakdown: dict
    requirements: List[ClassifiedRequirementResponse]


class ModelStatusResponse(BaseModel):
    status: str
    message: str
    model_dir: str
    version: Optional[str]
    test_accuracy: Optional[float]
    num_labels: Optional[int]


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_meeting_or_404(meeting_id: int, db: Session, user) -> Meeting:
    """Fetch a meeting and verify ownership through its project."""
    from app.models.project import Project

    meeting = (
        db.query(Meeting)
        .join(Project, Meeting.project_id == Project.id)
        .filter(Meeting.id == meeting_id, Project.owner_id == user.id)
        .first()
    )
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Meeting {meeting_id} not found.",
        )
    return meeting


# ── POST /meetings/{id}/classify ─────────────────────────────────────────────

@router.post(
    "/meetings/{meeting_id}/classify",
    response_model=ClassifyResponse,
    summary="Classify requirement candidates with DistilBERT",
)
def classify_meeting_requirements(
    meeting_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Run DistilBERT classification on all extracted requirement candidates
    for the given meeting.

    Prerequisites:
      - Meeting must have been through NLP processing (Phase 4)
      - Requirement candidates must exist in the database
      - Trained model must be present in models/distilbert_requirement_classifier/

    Each candidate's `category` and `ml_confidence` will be populated.
    """
    meeting = _get_meeting_or_404(meeting_id, db, current_user)

    # Guard: check model is available before doing any DB work
    if not DistilBERTService.is_trained():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "DistilBERT model has not been trained yet. "
                "Run: python -m app.ai.classifier.training.train "
                "from the backend/ directory first."
            ),
        )

    # Guard: NLP must have been run
    candidate_count = (
        db.query(RequirementCandidate)
        .filter(RequirementCandidate.meeting_id == meeting_id)
        .count()
    )
    if candidate_count == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "No requirement candidates found for this meeting. "
                "Run NLP processing (POST /meetings/{id}/process-nlp) first."
            ),
        )

    try:
        result = DistilBERTService.classify_meeting_requirements(db, meeting_id)
        return ClassifyResponse(
            success=True,
            meeting_id=meeting_id,
            classified=result["classified"],
            total=result["total"],
            category_breakdown=result.get("category_breakdown", {}),
            message=result["message"],
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Classification failed for meeting %d: %s", meeting_id, str(exc), exc_info=True)
        DistilBERTService.mark_failed(db, meeting_id, str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(exc)}",
        )


# ── GET /meetings/{id}/classified-requirements ────────────────────────────────

@router.get(
    "/meetings/{meeting_id}/classified-requirements",
    response_model=ClassifiedListResponse,
    summary="Get classified requirement candidates",
)
def get_classified_requirements(
    meeting_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return all requirement candidates with their DistilBERT classification results.
    Includes candidates that have been classified or are still in extracted state.
    """
    _get_meeting_or_404(meeting_id, db, current_user)

    candidates = (
        db.query(RequirementCandidate)
        .filter(
            RequirementCandidate.meeting_id == meeting_id,
            RequirementCandidate.is_active == True,
        )
        .order_by(RequirementCandidate.confidence_score.desc())
        .all()
    )

    # Build category breakdown from classified candidates only
    category_breakdown: dict[str, int] = {}
    classified_count = 0
    for c in candidates:
        if c.processing_status == "classified" and c.category:
            category_breakdown[c.category] = category_breakdown.get(c.category, 0) + 1
            classified_count += 1

    return ClassifiedListResponse(
        meeting_id=meeting_id,
        total=len(candidates),
        classified_count=classified_count,
        category_breakdown=category_breakdown,
        requirements=[
            ClassifiedRequirementResponse(
                id=c.id,
                meeting_id=c.meeting_id,
                speaker=c.speaker,
                sentence=c.sentence,
                clean_sentence=c.clean_sentence,
                category=c.category,
                ml_confidence=c.ml_confidence,
                confidence_score=c.confidence_score,
                processing_status=c.processing_status,
                classified_at=c.classified_at,
            )
            for c in candidates
        ],
    )


# ── GET /models/status ────────────────────────────────────────────────────────

@router.get(
    "/models/status",
    response_model=ModelStatusResponse,
    summary="Get DistilBERT model status",
)
def get_model_status(
    current_user=Depends(get_current_user),
):
    """
    Return the current status of the DistilBERT classifier model.

    Possible statuses:
      - untrained  : model has not been trained yet
      - available  : model exists on disk but not loaded into memory
      - loaded     : model is loaded and ready for inference
    """
    status_info = DistilBERTService.get_status()
    return ModelStatusResponse(**status_info)
