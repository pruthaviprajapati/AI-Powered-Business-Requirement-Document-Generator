"""
RequirementCandidate model – one row per extracted requirement sentence.

Phase 4: populated by NLPService
Phase 5: DistilBERT reads these rows and adds category + confidence
"""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


class RequirementCandidate(BaseModel):
    """
    A candidate software requirement extracted from a meeting transcript.
    Each row represents one sentence that passed the requirement heuristic.
    """

    __tablename__ = "requirement_candidates"

    # ── Ownership ─────────────────────────────────────────────────
    meeting_id = Column(
        Integer, ForeignKey("meetings.id"), nullable=False, index=True
    )

    # ── Source context ────────────────────────────────────────────
    speaker = Column(String(100), nullable=False, default="Unknown")

    # ── Sentence data ─────────────────────────────────────────────
    sentence = Column(Text, nullable=False)           # original sentence
    clean_sentence = Column(Text, nullable=False)     # cleaned sentence

    # ── NLP analysis (JSON strings) ───────────────────────────────
    tokens = Column(Text, nullable=True)              # JSON: [{text, lemma, pos, tag, dep}]
    lemmas = Column(Text, nullable=True)              # JSON: [lemma, ...]
    entities = Column(Text, nullable=True)            # JSON: [{text, label}]
    dependency_tree = Column(Text, nullable=True)     # JSON: [{text, dep, pos}]

    # ── Scoring ───────────────────────────────────────────────────
    confidence_score = Column(Float, default=0.0, nullable=False)  # Phase 4 heuristic

    # ── Phase 5 – DistilBERT classification ──────────────────────
    category = Column(String(100), nullable=True)     # Functional, Security, etc.
    ml_confidence = Column(Float, nullable=True)      # DistilBERT confidence score
    ml_model_version = Column(String(50), nullable=True)  # e.g. "1.0.0"
    classified_at = Column(DateTime, nullable=True)   # when classification ran

    # ── Processing state ──────────────────────────────────────────
    processing_status = Column(
        String(50), default="extracted", nullable=False
    )  # extracted | classified | classification_failed | reviewed | approved | rejected

    # ── Relationships ─────────────────────────────────────────────
    meeting = relationship("Meeting", back_populates="requirement_candidates")

    def __repr__(self) -> str:
        return (
            f"<RequirementCandidate id={self.id} "
            f"meeting={self.meeting_id} "
            f"status={self.processing_status!r}>"
        )
