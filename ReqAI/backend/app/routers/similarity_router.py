"""
similarity_router.py – Phase 6 semantic similarity API endpoints.

Endpoints:
  POST  /meetings/{id}/similarity/analyze   – Run similarity analysis
  GET   /meetings/{id}/similarity           – List all SIMILAR / POTENTIAL_DUPLICATE pairs
  GET   /meetings/{id}/duplicates           – List only duplicate-flagged pairs
  PATCH /similarity/{similarity_id}/review  – Set DUPLICATE_CONFIRMED or NOT_DUPLICATE
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.ai.similarity.services.similarity_service import SimilarityService
from app.auth.dependencies import get_current_user
from app.database.db import get_db
from app.models.meeting import Meeting
from app.core.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Phase 6 – Similarity Analysis"])


# ── Response schemas ──────────────────────────────────────────────────────────

class RequirementBrief(BaseModel):
    id: int
    sentence: str
    clean_sentence: str
    category: Optional[str]
    speaker: str
    ml_confidence: Optional[float]

    model_config = {"from_attributes": True}


class SimilarityPairResponse(BaseModel):
    id: int
    meeting_id: int
    requirement_id_1: int
    requirement_id_2: int
    similarity_score: float
    similarity_status: str
    requirement_1: RequirementBrief
    requirement_2: RequirementBrief
    created_at: Optional[object]
    updated_at: Optional[object]

    model_config = {"from_attributes": True}


class SimilarityAnalysisResponse(BaseModel):
    success: bool
    meeting_id: int
    requirements_analyzed: int
    total_pairs_stored: int
    similar_count: int
    potential_duplicates: int
    duplicate_threshold: float
    review_threshold: float
    message: str


class SimilarityListResponse(BaseModel):
    meeting_id: int
    total: int
    similar_count: int
    duplicate_count: int
    confirmed_count: int
    pairs: List[SimilarityPairResponse]


class ReviewRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"DUPLICATE_CONFIRMED", "NOT_DUPLICATE"}
        v = v.upper()
        if v not in allowed:
            raise ValueError(
                f"Invalid status '{v}'. Allowed: {sorted(allowed)}"
            )
        return v


class ReviewResponse(BaseModel):
    success: bool
    similarity_id: int
    new_status: str
    message: str


class SimilarityStatusResponse(BaseModel):
    model_name: str
    loaded: bool
    installed: bool
    duplicate_threshold: float
    review_threshold: float


# ── Helper ────────────────────────────────────────────────────────────────────

def _get_meeting_or_404(meeting_id: int, db: Session, user) -> Meeting:
    """Fetch meeting by id, verify ownership via project, raise 404 if not found."""
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


def _pair_to_response(pair) -> SimilarityPairResponse:
    """Convert a RequirementSimilarity ORM row to its response schema."""
    r1 = pair.requirement_1
    r2 = pair.requirement_2
    return SimilarityPairResponse(
        id=pair.id,
        meeting_id=pair.meeting_id,
        requirement_id_1=pair.requirement_id_1,
        requirement_id_2=pair.requirement_id_2,
        similarity_score=round(pair.similarity_score, 4),
        similarity_status=pair.similarity_status,
        requirement_1=RequirementBrief(
            id=r1.id,
            sentence=r1.sentence,
            clean_sentence=r1.clean_sentence,
            category=r1.category,
            speaker=r1.speaker,
            ml_confidence=r1.ml_confidence,
        ),
        requirement_2=RequirementBrief(
            id=r2.id,
            sentence=r2.sentence,
            clean_sentence=r2.clean_sentence,
            category=r2.category,
            speaker=r2.speaker,
            ml_confidence=r2.ml_confidence,
        ),
        created_at=pair.created_at,
        updated_at=pair.updated_at,
    )


# ── POST /meetings/{id}/similarity/analyze ────────────────────────────────────

@router.post(
    "/meetings/{meeting_id}/similarity/analyze",
    response_model=SimilarityAnalysisResponse,
    summary="Analyze semantic similarity for all requirements in a meeting",
)
def analyze_similarity(
    meeting_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate sentence embeddings for all RequirementCandidates in this meeting,
    compute pairwise cosine similarity, and store pairs that exceed the
    configured thresholds.

    Prerequisites:
      - Meeting must have had NLP processing completed (Phase 4).
      - sentence-transformers must be installed.

    Re-running this endpoint replaces all existing similarity data for the meeting.
    """
    _get_meeting_or_404(meeting_id, db, current_user)

    try:
        result = SimilarityService.analyze_meeting(db, meeting_id)
        return SimilarityAnalysisResponse(
            success=True,
            meeting_id=result["meeting_id"],
            requirements_analyzed=result["requirements_analyzed"],
            total_pairs_stored=result["total_pairs_stored"],
            similar_count=result["similar_count"],
            potential_duplicates=result["potential_duplicates"],
            duplicate_threshold=result["duplicate_threshold"],
            review_threshold=result["review_threshold"],
            message=(
                f"Analysis complete. "
                f"{result['similar_count']} similar pairs, "
                f"{result['potential_duplicates']} potential duplicates found."
            ),
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Similarity analysis failed for meeting %d: %s",
            meeting_id, str(exc), exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Similarity analysis failed: {str(exc)}",
        )


# ── GET /meetings/{id}/similarity ─────────────────────────────────────────────

@router.get(
    "/meetings/{meeting_id}/similarity",
    response_model=SimilarityListResponse,
    summary="Get all similarity pairs for a meeting",
)
def get_similarity_pairs(
    meeting_id: int = Path(..., gt=0),
    category: Optional[str] = Query(None, description="Filter by category name"),
    similarity_status: Optional[str] = Query(None, description="Filter by status"),
    min_score: Optional[float] = Query(None, ge=0.0, le=1.0, description="Minimum score"),
    speaker: Optional[str] = Query(None, description="Filter by speaker name"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return SIMILAR and POTENTIAL_DUPLICATE requirement pairs for a meeting.

    Supports optional filters:
      - category: only pairs where either requirement has this category
      - similarity_status: exact status match (SIMILAR, POTENTIAL_DUPLICATE, etc.)
      - min_score: minimum cosine similarity score
      - speaker: only pairs involving this speaker
    """
    _get_meeting_or_404(meeting_id, db, current_user)

    pairs = SimilarityService.get_similarity_pairs(
        db=db,
        meeting_id=meeting_id,
        category_filter=category,
        status_filter=similarity_status,
        min_score=min_score,
        speaker_filter=speaker,
    )

    # Count by status
    status_counts: dict[str, int] = {}
    for p in pairs:
        s = p.similarity_status
        status_counts[s] = status_counts.get(s, 0) + 1

    return SimilarityListResponse(
        meeting_id=meeting_id,
        total=len(pairs),
        similar_count=status_counts.get("SIMILAR", 0),
        duplicate_count=status_counts.get("POTENTIAL_DUPLICATE", 0),
        confirmed_count=status_counts.get("DUPLICATE_CONFIRMED", 0),
        pairs=[_pair_to_response(p) for p in pairs],
    )


# ── GET /meetings/{id}/duplicates ─────────────────────────────────────────────

@router.get(
    "/meetings/{meeting_id}/duplicates",
    response_model=SimilarityListResponse,
    summary="Get potential duplicate requirements",
)
def get_duplicates(
    meeting_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Return only POTENTIAL_DUPLICATE and DUPLICATE_CONFIRMED pairs for a meeting.
    This is a focused view of the highest-risk similarity pairs.
    """
    _get_meeting_or_404(meeting_id, db, current_user)

    pairs = SimilarityService.get_duplicates(db, meeting_id)

    status_counts: dict[str, int] = {}
    for p in pairs:
        s = p.similarity_status
        status_counts[s] = status_counts.get(s, 0) + 1

    return SimilarityListResponse(
        meeting_id=meeting_id,
        total=len(pairs),
        similar_count=0,
        duplicate_count=status_counts.get("POTENTIAL_DUPLICATE", 0),
        confirmed_count=status_counts.get("DUPLICATE_CONFIRMED", 0),
        pairs=[_pair_to_response(p) for p in pairs],
    )


# ── PATCH /similarity/{id}/review ────────────────────────────────────────────

@router.patch(
    "/similarity/{similarity_id}/review",
    response_model=ReviewResponse,
    summary="Review a similarity pair — confirm duplicate or mark as not duplicate",
)
def review_similarity(
    similarity_id: int = Path(..., gt=0),
    body: ReviewRequest = ...,
    meeting_id: int = Query(..., gt=0, description="Meeting ID (ownership check)"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Update the review status for a similarity pair.

    Allowed new statuses:
      - DUPLICATE_CONFIRMED  : user confirms these two requirements are duplicates
      - NOT_DUPLICATE        : user confirms they are NOT duplicates despite similar wording

    Note: the system never automatically deletes or merges requirements.
    Confirmation is purely informational for BRD generation (Phase 7).
    """
    pair = SimilarityService.update_review_status(
        db=db,
        similarity_id=similarity_id,
        new_status=body.status,
        user_id=current_user.id,
        meeting_id=meeting_id,
    )

    return ReviewResponse(
        success=True,
        similarity_id=pair.id,
        new_status=pair.similarity_status,
        message=f"Similarity pair {pair.id} marked as {pair.similarity_status}.",
    )


# ── GET /similarity/status ────────────────────────────────────────────────────

@router.get(
    "/similarity/status",
    response_model=SimilarityStatusResponse,
    summary="Get Sentence Transformer model status",
)
def get_similarity_status(
    current_user=Depends(get_current_user),
):
    """Return whether the Sentence Transformer model is installed and loaded."""
    info = SimilarityService.get_status()
    return SimilarityStatusResponse(**info)
