"""
Pydantic schemas for NLP / RequirementCandidate request/response validation.
"""
from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


# ── NLP Process response ──────────────────────────────────────────────────────

class NLPProcessResponse(BaseModel):
    message: str
    meeting_id: int
    nlp_status: str
    total_sentences: int
    candidate_count: int


# ── Requirement Candidate response ────────────────────────────────────────────

class RequirementCandidateResponse(BaseModel):
    id: int
    meeting_id: int
    speaker: str
    sentence: str
    clean_sentence: str
    tokens: Optional[Any] = None        # parsed JSON list
    lemmas: Optional[Any] = None        # parsed JSON list
    entities: Optional[Any] = None      # parsed JSON list
    dependency_tree: Optional[Any] = None
    confidence_score: float
    category: Optional[str] = None      # Phase 5 placeholder
    ml_confidence: Optional[float] = None
    processing_status: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class RequirementListResponse(BaseModel):
    meeting_id: int
    total: int
    nlp_status: str
    requirements: List[RequirementCandidateResponse]
