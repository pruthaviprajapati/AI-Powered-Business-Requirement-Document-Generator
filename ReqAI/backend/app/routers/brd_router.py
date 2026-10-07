"""
brd_router.py – Phase 7 API endpoints.

Endpoints:
  POST  /meetings/{id}/validate                 – LLM validation of requirements
  POST  /meetings/{id}/follow-up-questions      – Generate follow-up questions
  GET   /meetings/{id}/follow-up-questions      – List follow-up questions
  PATCH /follow-up-questions/{id}               – Answer / skip / edit question
  POST  /meetings/{id}/generate-brd             – Generate BRD document
  GET   /meetings/{id}/brd                      – BRD status + metadata
  GET   /brd/{document_id}/download             – Download DOCX
  GET   /groq/health                            – Groq API health check
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as FPath, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.llm.services.groq_service import GroqService
from app.auth.dependencies import get_current_user
from app.brd.schemas.brd_schema import (
    ValidationResponse, ValidationResultResponse,
    FollowUpQuestionResponse, FollowUpQuestionsListResponse,
    BRDDocumentResponse, BRDReadinessResponse,
)
from app.brd.services.brd_service import BRDService
from app.core.config import settings
from app.core.logging_config import get_logger
from app.database.db import get_db
from app.models.meeting import Meeting
from app.models.project import Project

logger = get_logger(__name__)
router = APIRouter(tags=["Phase 7 – LLM Validation & BRD"])


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_meeting(meeting_id: int, db: Session, user) -> Meeting:
    """Fetch meeting with ownership check via project.owner_id."""
    meeting = (
        db.query(Meeting)
        .join(Project, Meeting.project_id == Project.id)
        .filter(Meeting.id == meeting_id, Project.owner_id == user.id)
        .first()
    )
    if not meeting:
        raise HTTPException(status_code=404, detail=f"Meeting {meeting_id} not found.")
    return meeting


def _candidate_dicts(meeting_id: int, db: Session) -> list[dict]:
    from app.models.requirement_candidate import RequirementCandidate
    rows = (
        db.query(RequirementCandidate)
        .filter(
            RequirementCandidate.meeting_id == meeting_id,
            RequirementCandidate.is_active.is_(True),
        )
        .order_by(RequirementCandidate.id)
        .all()
    )
    return [
        {
            "id":            r.id,
            "sentence":      r.sentence,
            "clean_sentence": r.clean_sentence,
            "category":      r.category or "Unknown",
            "ml_confidence": r.ml_confidence,
            "speaker":       r.speaker,
        }
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# POST /meetings/{id}/validate
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/meetings/{meeting_id}/validate",
    response_model=ValidationResponse,
    summary="Run LLM validation on extracted requirements",
)
def validate_requirements(
    meeting_id: int = FPath(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Send classified requirements to Groq Llama for quality validation.

    The LLM evaluates each requirement for clarity, completeness, and ambiguity.
    It does NOT change the DistilBERT category.
    """
    _get_meeting(meeting_id, db, current_user)
    candidates = _candidate_dicts(meeting_id, db)

    if not candidates:
        raise HTTPException(422, "No requirement candidates found. Run NLP processing first.")

    result = GroqService.validate_requirements(candidates)

    counts = {"valid": 0, "needs_clarification": 0, "ambiguous": 0, "incomplete": 0}
    for r in result.requirements:
        counts[r.validation_status] = counts.get(r.validation_status, 0) + 1

    return ValidationResponse(
        success=True,
        meeting_id=meeting_id,
        total_validated=len(result.requirements),
        valid_count=counts["valid"],
        needs_clarification_count=counts["needs_clarification"],
        ambiguous_count=counts["ambiguous"],
        incomplete_count=counts["incomplete"],
        overall_quality=result.overall_quality,
        summary=result.summary,
        requirements=[ValidationResultResponse(**r.model_dump()) for r in result.requirements],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# POST /meetings/{id}/follow-up-questions
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/meetings/{meeting_id}/follow-up-questions",
    response_model=FollowUpQuestionsListResponse,
    summary="Generate follow-up questions with LLM",
)
def generate_follow_up_questions(
    meeting_id: int = FPath(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate specific clarification questions based on validation issues and
    gaps in the requirement set. Existing questions for this meeting are replaced.
    """
    from app.models.follow_up_question import FollowUpQuestion

    _get_meeting(meeting_id, db, current_user)
    candidates = _candidate_dicts(meeting_id, db)

    if not candidates:
        raise HTTPException(422, "No requirement candidates found.")

    # Validate first to get issues
    validation = GroqService.validate_requirements(candidates)
    validation_issues = [r.model_dump() for r in validation.requirements]

    # Detect missing information
    missing_areas = GroqService.detect_missing_information(candidates)

    # Generate questions
    questions_response = GroqService.generate_follow_up_questions(
        candidates=candidates,
        validation_issues=validation_issues,
        missing_areas=missing_areas,
        max_questions=15,
    )

    # Clear existing questions and re-persist
    db.query(FollowUpQuestion).filter(
        FollowUpQuestion.meeting_id == meeting_id
    ).delete()

    new_questions = []
    for q in questions_response.questions:
        row = FollowUpQuestion(
            meeting_id=meeting_id,
            requirement_id=q.requirement_id,
            question=q.question,
            reason=q.reason,
            priority=q.priority,
            status="OPEN",
        )
        db.add(row)
        new_questions.append(row)

    db.commit()
    for q in new_questions:
        db.refresh(q)

    return _build_questions_list_response(meeting_id, new_questions)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /meetings/{id}/follow-up-questions
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/meetings/{meeting_id}/follow-up-questions",
    response_model=FollowUpQuestionsListResponse,
    summary="Get follow-up questions for a meeting",
)
def get_follow_up_questions(
    meeting_id: int = FPath(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.follow_up_question import FollowUpQuestion

    _get_meeting(meeting_id, db, current_user)
    questions = (
        db.query(FollowUpQuestion)
        .filter(FollowUpQuestion.meeting_id == meeting_id)
        .order_by(FollowUpQuestion.id)
        .all()
    )
    return _build_questions_list_response(meeting_id, questions)


def _build_questions_list_response(meeting_id: int, questions: list) -> FollowUpQuestionsListResponse:
    status_counts = {"OPEN": 0, "ANSWERED": 0, "SKIPPED": 0}
    for q in questions:
        status_counts[q.status] = status_counts.get(q.status, 0) + 1

    return FollowUpQuestionsListResponse(
        meeting_id=meeting_id,
        total=len(questions),
        open_count=status_counts["OPEN"],
        answered_count=status_counts["ANSWERED"],
        skipped_count=status_counts["SKIPPED"],
        questions=[FollowUpQuestionResponse.model_validate(q) for q in questions],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# PATCH /follow-up-questions/{id}
# ═══════════════════════════════════════════════════════════════════════════════

class UpdateQuestionRequest(BaseModel):
    status: Optional[str] = None   # ANSWERED | SKIPPED | OPEN
    answer: Optional[str] = None
    question: Optional[str] = None  # allow editing the question text


@router.patch(
    "/follow-up-questions/{question_id}",
    response_model=FollowUpQuestionResponse,
    summary="Answer, skip, or edit a follow-up question",
)
def update_follow_up_question(
    question_id: int = FPath(..., gt=0),
    body: UpdateQuestionRequest = ...,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.follow_up_question import FollowUpQuestion

    question = db.query(FollowUpQuestion).filter(FollowUpQuestion.id == question_id).first()
    if not question:
        raise HTTPException(404, f"Question {question_id} not found.")

    # Ownership check via meeting
    meeting = (
        db.query(Meeting)
        .join(Project, Meeting.project_id == Project.id)
        .filter(Meeting.id == question.meeting_id, Project.owner_id == current_user.id)
        .first()
    )
    if not meeting:
        raise HTTPException(403, "Not authorised to update this question.")

    if body.status is not None:
        allowed_statuses = {"OPEN", "ANSWERED", "SKIPPED"}
        s = body.status.upper()
        if s not in allowed_statuses:
            raise HTTPException(422, f"Invalid status '{s}'. Allowed: {sorted(allowed_statuses)}")
        question.status = s

    if body.answer is not None:
        question.answer = body.answer.strip()
        if question.answer:
            question.status = "ANSWERED"

    if body.question is not None and body.question.strip():
        question.question = body.question.strip()

    db.commit()
    db.refresh(question)
    return FollowUpQuestionResponse.model_validate(question)


# ═══════════════════════════════════════════════════════════════════════════════
# POST /meetings/{id}/generate-brd
# ═══════════════════════════════════════════════════════════════════════════════

@router.post(
    "/meetings/{meeting_id}/generate-brd",
    response_model=BRDDocumentResponse,
    summary="Generate Business Requirement Document",
)
def generate_brd(
    meeting_id: int = FPath(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Generate a BRD DOCX for the meeting.

    Workflow:
      1. Gather classified requirements + answered questions
      2. Call Groq to generate structured BRD content
      3. Validate JSON with Pydantic
      4. Build DOCX with python-docx
      5. Store BRDDocument record

    The user must explicitly trigger this — it is NOT automatic.
    """
    doc = BRDService.generate(db, meeting_id, current_user.id)
    return BRDDocumentResponse.model_validate(doc)


# ═══════════════════════════════════════════════════════════════════════════════
# GET /meetings/{id}/brd
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/meetings/{meeting_id}/brd",
    response_model=BRDReadinessResponse,
    summary="Get BRD readiness status and latest document info",
)
def get_brd_status(
    meeting_id: int = FPath(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.requirement_candidate import RequirementCandidate
    from app.models.follow_up_question import FollowUpQuestion
    from app.models.requirement_similarity import RequirementSimilarity

    _get_meeting(meeting_id, db, current_user)

    total_reqs = db.query(RequirementCandidate).filter(
        RequirementCandidate.meeting_id == meeting_id,
        RequirementCandidate.is_active.is_(True),
    ).count()

    classified = db.query(RequirementCandidate).filter(
        RequirementCandidate.meeting_id == meeting_id,
        RequirementCandidate.is_active.is_(True),
        RequirementCandidate.processing_status == "classified",
    ).count()

    pot_dups = db.query(RequirementSimilarity).filter(
        RequirementSimilarity.meeting_id == meeting_id,
        RequirementSimilarity.similarity_status == "POTENTIAL_DUPLICATE",
    ).count()

    open_q = db.query(FollowUpQuestion).filter(
        FollowUpQuestion.meeting_id == meeting_id,
        FollowUpQuestion.status == "OPEN",
    ).count()

    answered_q = db.query(FollowUpQuestion).filter(
        FollowUpQuestion.meeting_id == meeting_id,
        FollowUpQuestion.status == "ANSWERED",
    ).count()

    last_brd = BRDService.get_latest(db, meeting_id)
    ready = total_reqs > 0

    msg_parts = []
    if total_reqs == 0:
        msg_parts.append("No requirements found — run NLP extraction first.")
    else:
        msg_parts.append(f"{total_reqs} requirements found.")
    if pot_dups > 0:
        msg_parts.append(f"{pot_dups} potential duplicates need review.")
    if open_q > 0:
        msg_parts.append(f"{open_q} open questions.")

    return BRDReadinessResponse(
        meeting_id=meeting_id,
        requirements_found=total_reqs,
        requirements_classified=classified,
        potential_duplicates=pot_dups,
        validation_issues=0,
        open_questions=open_q,
        answered_questions=answered_q,
        ready=ready,
        message=" ".join(msg_parts) or "Ready to generate BRD.",
        last_brd=BRDDocumentResponse.model_validate(last_brd) if last_brd else None,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /brd/{document_id}/download
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/brd/{document_id}/download",
    summary="Download a generated BRD DOCX",
)
def download_brd(
    document_id: int = FPath(..., gt=0),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Securely serve the generated DOCX file.
    Verifies that the requesting user owns the meeting this BRD belongs to.
    """
    brd_doc = BRDService.get_by_id(db, document_id)
    if not brd_doc:
        raise HTTPException(404, f"BRD document {document_id} not found.")

    # Ownership check
    meeting = (
        db.query(Meeting)
        .join(Project, Meeting.project_id == Project.id)
        .filter(Meeting.id == brd_doc.meeting_id, Project.owner_id == current_user.id)
        .first()
    )
    if not meeting:
        raise HTTPException(403, "Not authorised to download this document.")

    if brd_doc.generation_status != "COMPLETED" or not brd_doc.file_path:
        raise HTTPException(422, "BRD document is not yet generated or failed.")

    file_path = settings.BASE_DIR / brd_doc.file_path
    if not file_path.exists():
        raise HTTPException(404, "BRD file not found on disk.")

    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=brd_doc.file_name or f"BRD_{document_id}.docx",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GET /groq/health
# ═══════════════════════════════════════════════════════════════════════════════

@router.get(
    "/groq/health",
    summary="Check Groq API connectivity",
)
def groq_health(current_user=Depends(get_current_user)):
    """Ping Groq to verify the API key and connectivity."""
    return GroqService.health_check()
