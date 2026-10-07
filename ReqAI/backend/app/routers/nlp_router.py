"""
NLP router – requirement candidate extraction endpoints.

Endpoints:
  POST /api/v1/meetings/{id}/process-nlp      – run NLP pipeline
  GET  /api/v1/meetings/{id}/requirements     – list all candidates
  GET  /api/v1/meetings/{id}/requirements/{req_id} – single candidate
"""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.nlp.services.nlp_service import NLPService
from app.auth.dependencies import get_current_user
from app.core.logging_config import get_logger
from app.database.db import get_db
from app.models.requirement_candidate import RequirementCandidate
from app.models.user import User
from app.schemas.requirement_schema import (
    NLPProcessResponse,
    RequirementCandidateResponse,
    RequirementListResponse,
)
from app.services.meeting_service import MeetingService

router = APIRouter(prefix="/meetings", tags=["NLP & Requirements"])
logger = get_logger(__name__)


def _parse_json_field(value) -> list:
    """Safely parse a JSON string field into a Python list."""
    if value is None:
        return []
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _build_candidate_response(c: RequirementCandidate) -> RequirementCandidateResponse:
    """Convert ORM object to response schema, parsing JSON fields."""
    return RequirementCandidateResponse(
        id=c.id,
        meeting_id=c.meeting_id,
        speaker=c.speaker,
        sentence=c.sentence,
        clean_sentence=c.clean_sentence,
        tokens=_parse_json_field(c.tokens),
        lemmas=_parse_json_field(c.lemmas),
        entities=_parse_json_field(c.entities),
        dependency_tree=_parse_json_field(c.dependency_tree),
        confidence_score=c.confidence_score,
        category=c.category,
        ml_confidence=c.ml_confidence,
        processing_status=c.processing_status,
        is_active=c.is_active,
        created_at=c.created_at,
    )


# ── POST /meetings/{id}/process-nlp ──────────────────────────────────────────

@router.post("/{meeting_id}/process-nlp", response_model=NLPProcessResponse)
def process_nlp(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run the full NLP pipeline on a meeting's speaker transcript.

    Prerequisites:
      - Transcription must be completed (transcript field exists)
      - Uses speaker_transcript (Phase 3) if available,
        falls back to raw transcript

    Flow:
      1. Load spaCy model
      2. Clean + segment transcript
      3. Tokenize, lemmatize, POS, NER every sentence
      4. Score requirement candidates
      5. Save RequirementCandidate rows
      6. Return summary
    """
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    # ── Guards ─────────────────────────────────────────────────────
    if not meeting.transcript and not meeting.speaker_transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No transcript found. Please run transcription first.",
        )

    if meeting.nlp_status == "processing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="NLP processing is already in progress.",
        )

    # Prefer Phase 3 speaker transcript; fall back to raw transcript
    transcript_input = meeting.speaker_transcript or meeting.transcript

    # Mark as processing
    meeting.nlp_status = "processing"
    db.commit()

    try:
        result = NLPService.process(meeting.id, transcript_input)
        NLPService.save_results(db, meeting, result)
    except HTTPException as exc:
        NLPService.mark_failed(db, meeting, exc.detail)
        raise
    except Exception as exc:
        error_msg = f"NLP processing failed: {str(exc)}"
        NLPService.mark_failed(db, meeting, error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    db.refresh(meeting)
    logger.info(
        "NLP complete for meeting %d: %d candidates", meeting_id, result.candidate_count
    )

    return NLPProcessResponse(
        message="NLP processing completed successfully.",
        meeting_id=meeting.id,
        nlp_status=meeting.nlp_status,
        total_sentences=result.total_sentences,
        candidate_count=result.candidate_count,
    )


# ── GET /meetings/{id}/requirements ──────────────────────────────────────────

@router.get("/{meeting_id}/requirements", response_model=RequirementListResponse)
def list_requirements(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return all active requirement candidates for a meeting."""
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    candidates = (
        db.query(RequirementCandidate)
        .filter(
            RequirementCandidate.meeting_id == meeting_id,
            RequirementCandidate.is_active == True,
        )
        .order_by(RequirementCandidate.id.asc())
        .all()
    )

    return RequirementListResponse(
        meeting_id=meeting_id,
        total=len(candidates),
        nlp_status=meeting.nlp_status,
        requirements=[_build_candidate_response(c) for c in candidates],
    )


# ── GET /meetings/{id}/requirements/{req_id} ─────────────────────────────────

@router.get(
    "/{meeting_id}/requirements/{requirement_id}",
    response_model=RequirementCandidateResponse,
)
def get_requirement(
    meeting_id: int,
    requirement_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return a single requirement candidate by ID."""
    # Verify meeting ownership
    MeetingService.get_by_id(db, meeting_id, current_user.id)

    candidate = (
        db.query(RequirementCandidate)
        .filter(
            RequirementCandidate.id == requirement_id,
            RequirementCandidate.meeting_id == meeting_id,
            RequirementCandidate.is_active == True,
        )
        .first()
    )

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Requirement candidate not found.",
        )

    return _build_candidate_response(candidate)
