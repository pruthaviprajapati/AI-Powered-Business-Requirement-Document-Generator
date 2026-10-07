"""
RequirementSimilarity model – stores semantic similarity scores between pairs
of RequirementCandidate rows.

Phase 6: populated by SimilarityService.
One row per (requirement_id_1, requirement_id_2) pair — always stored with
requirement_id_1 < requirement_id_2 to avoid A-B / B-A duplicates.

similarity_status lifecycle:
  NOT_SIMILAR        – score below lower threshold (stored for completeness when needed)
  SIMILAR            – score between review_threshold and duplicate_threshold
  POTENTIAL_DUPLICATE – score at or above duplicate_threshold
  REVIEWED           – a user has opened the review workflow
  DUPLICATE_CONFIRMED – user confirmed these two are duplicates
  NOT_DUPLICATE      – user confirmed these are NOT duplicates despite high score
"""
from sqlalchemy import Column, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


class RequirementSimilarity(BaseModel):
    """Semantic similarity pair between two RequirementCandidate rows."""

    __tablename__ = "requirement_similarities"

    # ── Ownership ─────────────────────────────────────────────────
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)

    # ── The two candidates being compared ─────────────────────────
    # Invariant: requirement_id_1 < requirement_id_2 (no duplicate pairs)
    requirement_id_1 = Column(
        Integer,
        ForeignKey("requirement_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    requirement_id_2 = Column(
        Integer,
        ForeignKey("requirement_candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Similarity score ──────────────────────────────────────────
    similarity_score = Column(Float, nullable=False)  # cosine similarity [0.0, 1.0]

    # ── Status ────────────────────────────────────────────────────
    similarity_status = Column(
        String(50),
        nullable=False,
        default="SIMILAR",
        index=True,
    )
    # NOT_SIMILAR | SIMILAR | POTENTIAL_DUPLICATE |
    # REVIEWED | DUPLICATE_CONFIRMED | NOT_DUPLICATE

    # ── Relationships ─────────────────────────────────────────────
    meeting = relationship("Meeting")
    requirement_1 = relationship(
        "RequirementCandidate", foreign_keys=[requirement_id_1]
    )
    requirement_2 = relationship(
        "RequirementCandidate", foreign_keys=[requirement_id_2]
    )

    # ── Unique constraint: one row per ordered pair per meeting ───
    __table_args__ = (
        UniqueConstraint(
            "meeting_id",
            "requirement_id_1",
            "requirement_id_2",
            name="uq_similarity_pair",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<RequirementSimilarity "
            f"req1={self.requirement_id_1} "
            f"req2={self.requirement_id_2} "
            f"score={self.similarity_score:.3f} "
            f"status={self.similarity_status!r}>"
        )
