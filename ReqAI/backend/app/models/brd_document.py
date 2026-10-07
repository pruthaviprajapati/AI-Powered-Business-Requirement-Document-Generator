"""
BRDDocument model – tracks generated Business Requirement Documents.

Phase 7: one row per BRD generation attempt for a meeting.
"""
from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


class BRDDocument(BaseModel):
    """A generated BRD file linked to a meeting."""

    __tablename__ = "brd_documents"

    # ── Ownership ─────────────────────────────────────────────────
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False, index=True)

    # ── File info ──────────────────────────────────────────────────
    file_path = Column(String(500), nullable=True)    # relative path under generated/brd/
    file_name = Column(String(300), nullable=True)    # e.g. REQAI_ProjectName_2026-08-16.docx

    # ── Generation metadata ───────────────────────────────────────
    generation_status = Column(
        String(50), default="GENERATING", nullable=False
    )  # GENERATING | COMPLETED | FAILED

    model_name  = Column(String(100), nullable=True)  # Groq model used
    error_message = Column(Text, nullable=True)        # populated on FAILED

    # ── Relationships ─────────────────────────────────────────────
    meeting = relationship("Meeting")

    def __repr__(self) -> str:
        return (
            f"<BRDDocument id={self.id} "
            f"meeting={self.meeting_id} "
            f"status={self.generation_status!r}>"
        )
