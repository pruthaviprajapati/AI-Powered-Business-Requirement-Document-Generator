"""
Meeting model – stores meeting metadata and AI processing state.

Phase 1: Only basic meeting info is used.
Phase 2+: audio_file, transcript, and processing fields will be populated
          by the Speech Recognition → NLP → ML pipeline.
"""
from sqlalchemy import Column, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base_model import BaseModel


class Meeting(BaseModel):
    """Represents a recorded requirement-gathering meeting."""

    __tablename__ = "meetings"

    # ── Basic Information ─────────────────────────────────────────
    title = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    meeting_date = Column(String(50), nullable=True)   # ISO date string
    duration_minutes = Column(Float, nullable=True)
    participants = Column(Text, nullable=True)          # comma-separated names

    # ── Ownership ─────────────────────────────────────────────────
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    # ── Phase 2 – Speech Recognition placeholders ─────────────────
    audio_file = Column(String(500), nullable=True)    # path to uploaded audio
    audio_file_size = Column(Integer, nullable=True)   # bytes

    # ── Phase 2 – Transcription placeholders ──────────────────────
    transcript = Column(Text, nullable=True)            # raw transcript text
    transcript_language = Column(String(20), nullable=True)

    # ── Phase 2/3 – ML Processing placeholders ────────────────────
    processing_status = Column(
        String(50), default="pending", nullable=False
    )  # pending | processing | completed | failed

    # ── Phase 3 – BRD Generation placeholders ─────────────────────
    generated_brd = Column(Text, nullable=True)        # generated BRD content
    brd_file_path = Column(String(500), nullable=True) # path to .docx file

    # ── AI Metadata placeholders ───────────────────────────────────
    requirements_count = Column(Integer, default=0, nullable=False)
    follow_up_questions = Column(Text, nullable=True)   # JSON string

    # ── Relationships ─────────────────────────────────────────────
    project = relationship("Project", back_populates="meetings")

    def __repr__(self) -> str:
        return f"<Meeting id={self.id} title={self.title!r} status={self.processing_status!r}>"
