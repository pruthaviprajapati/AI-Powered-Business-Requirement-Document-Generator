"""
Pydantic schemas for Meeting request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ── Create ────────────────────────────────────────────────────────────────────

class MeetingCreate(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_date: Optional[str] = None
    duration_minutes: Optional[float] = None
    participants: Optional[str] = None
    project_id: int


# ── Update ────────────────────────────────────────────────────────────────────

class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    meeting_date: Optional[str] = None
    duration_minutes: Optional[float] = None
    participants: Optional[str] = None
    processing_status: Optional[str] = None


# ── Response ──────────────────────────────────────────────────────────────────

class MeetingResponse(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    meeting_date: Optional[str] = None
    duration_minutes: Optional[float] = None
    participants: Optional[str] = None
    project_id: int

    # Phase 2 – audio fields
    audio_file_path: Optional[str] = None
    audio_file_size: Optional[int] = None
    audio_original_name: Optional[str] = None

    # Phase 2 – transcript fields
    transcript: Optional[str] = None
    transcript_language: Optional[str] = None

    # Phase 2 – processing state
    processing_status: str
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None

    # Phase 3 – speaker diarization
    speaker_transcript: Optional[str] = None
    speaker_count: int = 0
    diarization_status: str = "pending"

    # Phase 4 – NLP processing
    nlp_status: str = "pending"

    # Phase 5 placeholders
    generated_brd: Optional[str] = None
    brd_file_path: Optional[str] = None
    requirements_count: int

    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MeetingListResponse(BaseModel):
    total: int
    meetings: list[MeetingResponse]


# ── Audio / Transcription responses ──────────────────────────────────────────

class AudioUploadResponse(BaseModel):
    message: str
    meeting_id: int
    audio_file_path: str
    audio_file_size: int
    audio_original_name: str
    processing_status: str


class TranscriptResponse(BaseModel):
    meeting_id: int
    transcript: Optional[str]
    transcript_language: Optional[str]
    processing_status: str
    processing_started_at: Optional[datetime] = None
    processing_completed_at: Optional[datetime] = None
    processing_error: Optional[str] = None


# ── Speaker Diarization schemas ───────────────────────────────────────────────

class SpeakerSegment(BaseModel):
    """A single speaker turn with timestamps and text."""
    speaker: str          # e.g. "Speaker 1"
    speaker_index: int    # 0-based index (for colour assignment)
    start: float          # seconds
    end: float            # seconds
    start_fmt: str        # "MM:SS" formatted
    end_fmt: str
    text: str             # speech text for this segment


class DiarizeResponse(BaseModel):
    meeting_id: int
    diarization_status: str
    speaker_count: int
    segments: list[SpeakerSegment]
    speaker_transcript: str           # full formatted text transcript
    processing_error: Optional[str] = None


class SpeakerTranscriptResponse(BaseModel):
    meeting_id: int
    diarization_status: str
    speaker_count: int
    speaker_transcript: Optional[str]
    segments: list[SpeakerSegment]


class SpeakerSummaryResponse(BaseModel):
    meeting_id: int
    speaker_count: int
    diarization_status: str
    speakers: list[dict]   # [{speaker, segment_count, total_duration, percentage}]
    total_duration: float
