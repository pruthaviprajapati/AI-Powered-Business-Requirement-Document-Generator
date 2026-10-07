"""
Speaker router – diarization endpoints.

Endpoints:
  POST /meetings/{id}/diarize            – run speaker diarization
  GET  /meetings/{id}/speaker-transcript – get labelled transcript
  GET  /meetings/{id}/speaker-summary    – per-speaker statistics
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.ai.speaker.services.speaker_service import SpeakerService
from app.ai.speaker.utils.diarization_utils import (
    build_speaker_segments,
    assign_speaker_labels,
    compute_speaker_summary,
)
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.logging_config import get_logger
from app.database.db import get_db
from app.models.user import User
from app.schemas.meeting_schema import (
    DiarizeResponse,
    SpeakerSegment,
    SpeakerSummaryResponse,
    SpeakerTranscriptResponse,
)
from app.services.meeting_service import MeetingService

router = APIRouter(prefix="/meetings", tags=["Speaker Diarization"])
logger = get_logger(__name__)


def _parse_stored_segments(meeting) -> list[dict]:
    """
    Re-parse stored speaker segments from speaker_data and speaker_transcript.
    Returns list of SpeakerSegment-compatible dicts.
    """
    if not meeting.speaker_data:
        return []

    try:
        turns = json.loads(meeting.speaker_data)
    except (json.JSONDecodeError, TypeError):
        return []

    # Rebuild label map from stored turns
    raw_speakers_ordered = []
    seen = set()
    for t in turns:
        sp = t.get("speaker", "SPEAKER_00")
        if sp not in seen:
            raw_speakers_ordered.append(sp)
            seen.add(sp)

    label_map = assign_speaker_labels(raw_speakers_ordered)

    # We need whisper segments to rebuild. If speaker_data has text fields, use them.
    # Fallback: build segments purely from diarization turns (no word-level text)
    whisper_segments = []
    for t in turns:
        whisper_segments.append({
            "start": t["start"],
            "end": t["end"],
            "text": t.get("text", ""),
        })

    from app.ai.speaker.utils.diarization_utils import (
        merge_whisper_and_diarization,
        build_speaker_segments as _build,
    )
    merged = merge_whisper_and_diarization(whisper_segments, turns)
    return _build(merged, label_map)


# ── POST /meetings/{id}/diarize ───────────────────────────────────────────────

@router.post("/{meeting_id}/diarize", response_model=DiarizeResponse)
def diarize_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run speaker diarization on the meeting's audio.
    Requires:
      1. Audio file must be uploaded (audio_file_path set)
      2. Transcription must be completed (transcript exists + whisper segments in speaker_data)

    Flow:
      1. Validate prerequisites
      2. Load Whisper segments from speaker_data (stored in Phase 2)
      3. Run SpeakerService.process()
      4. Save results
      5. Return DiarizeResponse
    """
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    # ── Guards ─────────────────────────────────────────────────────
    if not meeting.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file found. Please upload audio and transcribe first.",
        )

    if not meeting.transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcription not found. Please run transcription before diarization.",
        )

    if meeting.diarization_status == "diarizing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Diarization is already in progress for this meeting.",
        )

    # ── Load Whisper segments saved in Phase 2 ─────────────────────
    whisper_segments = []
    if meeting.speaker_data:
        try:
            stored = json.loads(meeting.speaker_data)
            # Phase 2 stored raw whisper segments: [{start, end, text}]
            # Check if they look like whisper segments (have 'text' key, no 'speaker' key)
            if stored and "text" in stored[0] and "speaker" not in stored[0]:
                whisper_segments = stored
        except (json.JSONDecodeError, TypeError, IndexError):
            whisper_segments = []

    # If no Whisper segments available, build fallback from transcript
    if not whisper_segments and meeting.transcript:
        whisper_segments = [{"start": 0.0, "end": 60.0, "text": meeting.transcript}]

    # ── Mark as diarizing ──────────────────────────────────────────
    meeting.diarization_status = "diarizing"
    db.commit()

    # ── Resolve audio path ─────────────────────────────────────────
    audio_full_path = settings.BASE_DIR / meeting.audio_file_path

    try:
        result = SpeakerService.process(audio_full_path, whisper_segments)
        SpeakerService.save_diarization(db, meeting, result)
    except HTTPException as exc:
        SpeakerService.mark_failed(db, meeting, exc.detail)
        raise
    except Exception as exc:
        error_msg = f"Unexpected diarization error: {str(exc)}"
        SpeakerService.mark_failed(db, meeting, error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    db.refresh(meeting)

    # Build response segments from result
    segments = [SpeakerSegment(**s) for s in result["speaker_segments"]]

    return DiarizeResponse(
        meeting_id=meeting.id,
        diarization_status=meeting.diarization_status,
        speaker_count=meeting.speaker_count,
        segments=segments,
        speaker_transcript=meeting.speaker_transcript or "",
    )


# ── GET /meetings/{id}/speaker-transcript ─────────────────────────────────────

@router.get("/{meeting_id}/speaker-transcript", response_model=SpeakerTranscriptResponse)
def get_speaker_transcript(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the speaker-labelled transcript and segment list."""
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    segments = _parse_stored_segments(meeting)

    return SpeakerTranscriptResponse(
        meeting_id=meeting.id,
        diarization_status=meeting.diarization_status,
        speaker_count=meeting.speaker_count,
        speaker_transcript=meeting.speaker_transcript,
        segments=[SpeakerSegment(**s) for s in segments] if segments else [],
    )


# ── GET /meetings/{id}/speaker-summary ────────────────────────────────────────

@router.get("/{meeting_id}/speaker-summary", response_model=SpeakerSummaryResponse)
def get_speaker_summary(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return per-speaker talk-time statistics."""
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    if meeting.diarization_status not in ("completed", "skipped"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Diarization has not been completed for this meeting.",
        )

    segments = _parse_stored_segments(meeting)
    speaker_stats = compute_speaker_summary(segments)
    total_duration = sum(s["total_duration"] for s in speaker_stats)

    return SpeakerSummaryResponse(
        meeting_id=meeting.id,
        speaker_count=meeting.speaker_count,
        diarization_status=meeting.diarization_status,
        speakers=speaker_stats,
        total_duration=round(total_duration, 2),
    )
