"""
Meeting model – stores meeting metadata and AI processing state.

Phase 1: Basic meeting info.
Phase 2: audio_file_path, transcript, processing timestamps.
Phase 3+: speaker_data, requirements, BRD generation.
"""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
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

    # ── Phase 2 – Audio Storage ───────────────────────────────────
    audio_file_path = Column(String(500), nullable=True)   # relative path under uploads/audio/
    audio_file_size = Column(Integer, nullable=True)        # bytes
    audio_original_name = Column(String(300), nullable=True)  # original uploaded filename

    # ── Phase 2 – Transcription ───────────────────────────────────
    transcript = Column(Text, nullable=True)               # raw transcript text
    transcript_language = Column(String(20), nullable=True) # detected/forced language

    # ── Phase 2 – Processing State ────────────────────────────────
    processing_status = Column(
        String(50), default="pending", nullable=False
    )  # pending | uploading | transcribing | completed | failed
    processing_started_at = Column(DateTime(timezone=True), nullable=True)
    processing_completed_at = Column(DateTime(timezone=True), nullable=True)
    processing_error = Column(Text, nullable=True)         # last error message if failed

    # ── Phase 3 – Speaker Identification ─────────────────────────
    speaker_data = Column(Text, nullable=True)             # JSON: raw diarization segments
    speaker_transcript = Column(Text, nullable=True)       # formatted speaker-labelled transcript
    speaker_count = Column(Integer, default=0, nullable=False)  # number of unique speakers detected
    diarization_status = Column(
        String(50), default="pending", nullable=False
    )  # pending | diarizing | completed | failed | skipped

    # ── Phase 4 – NLP Processing ──────────────────────────────────
    nlp_status = Column(
        String(50), default="pending", nullable=False
    )  # pending | processing | completed | failed

    # ── Phase 5 – BRD Generation placeholders ─────────────────────
    generated_brd = Column(Text, nullable=True)
    brd_file_path = Column(String(500), nullable=True)

    # ── AI Metadata ───────────────────────────────────────────────
    requirements_count = Column(Integer, default=0, nullable=False)
    follow_up_questions = Column(Text, nullable=True)      # JSON string

    # ── Relationships ─────────────────────────────────────────────
    project = relationship("Project", back_populates="meetings")
    requirement_candidates = relationship(
        "RequirementCandidate",
        back_populates="meeting",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self) -> str:
        return f"<Meeting id={self.id} title={self.title!r} status={self.processing_status!r}>"
