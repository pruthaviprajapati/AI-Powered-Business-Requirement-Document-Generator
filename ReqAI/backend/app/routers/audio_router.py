"""
Audio router – handles audio upload, browser recording submission, and transcription.

Endpoints:
  POST /meetings/{id}/upload-audio   – upload audio file from disk
  POST /meetings/{id}/recording      – submit recorded audio blob from browser
  POST /meetings/{id}/transcribe     – trigger Whisper transcription
  GET  /meetings/{id}/transcript     – retrieve stored transcript
"""
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.ai.speech.services.speech_service import SpeechService
from app.ai.speech.utils.audio_utils import (
    delete_audio_file,
    get_audio_relative_path,
    get_audio_storage_path,
    get_unique_audio_filename,
    save_audio_file,
    validate_audio_file,
)
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.core.logging_config import get_logger
from app.database.db import get_db
from app.models.user import User
from app.schemas.common_schema import SuccessResponse
from app.schemas.meeting_schema import AudioUploadResponse, TranscriptResponse
from app.services.meeting_service import MeetingService

router = APIRouter(prefix="/meetings", tags=["Audio & Transcription"])
logger = get_logger(__name__)


# ── Upload audio file ─────────────────────────────────────────────────────────

@router.post("/{meeting_id}/upload-audio", response_model=AudioUploadResponse)
async def upload_audio(
    meeting_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload an audio file (MP3, WAV, M4A, WEBM, OGG, FLAC) for a meeting.
    Replaces any previously uploaded audio for the same meeting.
    """
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    # Validate extension and content type
    validate_audio_file(file)

    # If meeting already has an audio file, delete it
    if meeting.audio_file_path:
        delete_audio_file(meeting.audio_file_path)

    # Generate unique filename and save
    unique_name = get_unique_audio_filename(file.filename)
    file_size = await save_audio_file(file, unique_name)
    relative_path = get_audio_relative_path(unique_name)

    # Persist metadata in the database
    meeting.audio_file_path = relative_path
    meeting.audio_file_size = file_size
    meeting.audio_original_name = file.filename
    meeting.processing_status = "uploaded"
    meeting.transcript = None                     # reset any previous transcript
    meeting.processing_error = None
    db.commit()
    db.refresh(meeting)

    logger.info("Audio uploaded for meeting id=%d: %s (%d bytes)", meeting_id, unique_name, file_size)

    return AudioUploadResponse(
        message="Audio file uploaded successfully.",
        meeting_id=meeting.id,
        audio_file_path=relative_path,
        audio_file_size=file_size,
        audio_original_name=file.filename,
        processing_status=meeting.processing_status,
    )


# ── Submit browser recording ──────────────────────────────────────────────────

@router.post("/{meeting_id}/recording", response_model=AudioUploadResponse)
async def submit_recording(
    meeting_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Accept a recorded audio blob from the browser MediaRecorder API.
    The browser sends a .webm file; treated identically to a file upload.
    """
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    # Browser recordings may arrive with content-type audio/webm and filename 'recording.webm'
    if not file.filename or file.filename.strip() == "":
        file.filename = "recording.webm"

    validate_audio_file(file)

    if meeting.audio_file_path:
        delete_audio_file(meeting.audio_file_path)

    unique_name = get_unique_audio_filename(file.filename)
    file_size = await save_audio_file(file, unique_name)
    relative_path = get_audio_relative_path(unique_name)

    meeting.audio_file_path = relative_path
    meeting.audio_file_size = file_size
    meeting.audio_original_name = f"recording_{meeting_id}.webm"
    meeting.processing_status = "uploaded"
    meeting.transcript = None
    meeting.processing_error = None
    db.commit()
    db.refresh(meeting)

    logger.info("Browser recording saved for meeting id=%d: %s", meeting_id, unique_name)

    return AudioUploadResponse(
        message="Recording saved successfully.",
        meeting_id=meeting.id,
        audio_file_path=relative_path,
        audio_file_size=file_size,
        audio_original_name=meeting.audio_original_name,
        processing_status=meeting.processing_status,
    )


# ── Transcribe ────────────────────────────────────────────────────────────────

@router.post("/{meeting_id}/transcribe", response_model=TranscriptResponse)
def transcribe_meeting(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Trigger Whisper transcription for a meeting's uploaded audio.

    Flow:
      1. Verify audio file exists
      2. Mark meeting as 'transcribing'
      3. Run SpeechService.transcribe_audio()
      4. Persist result via SpeechService.save_transcript()
      5. Return TranscriptResponse
    """
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    # Guard: must have an audio file
    if not meeting.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No audio file found for this meeting. Please upload audio first.",
        )

    # Guard: don't re-transcribe if already in progress
    if meeting.processing_status == "transcribing":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Transcription is already in progress for this meeting.",
        )

    # Mark as transcribing
    meeting.processing_status = "transcribing"
    meeting.processing_started_at = datetime.now(timezone.utc)
    meeting.processing_error = None
    db.commit()

    # Resolve full path
    audio_full_path = settings.BASE_DIR / meeting.audio_file_path

    try:
        result = SpeechService.transcribe_audio(audio_full_path)
        SpeechService.save_transcript(db, meeting, result)
    except HTTPException as exc:
        # Let SpeechService mark the failure in DB, then re-raise
        SpeechService.mark_failed(db, meeting, exc.detail)
        raise
    except Exception as exc:
        error_msg = f"Unexpected error during transcription: {str(exc)}"
        SpeechService.mark_failed(db, meeting, error_msg)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )

    db.refresh(meeting)

    return TranscriptResponse(
        meeting_id=meeting.id,
        transcript=meeting.transcript,
        transcript_language=meeting.transcript_language,
        processing_status=meeting.processing_status,
        processing_started_at=meeting.processing_started_at,
        processing_completed_at=meeting.processing_completed_at,
    )


# ── Get transcript ────────────────────────────────────────────────────────────

@router.get("/{meeting_id}/transcript", response_model=TranscriptResponse)
def get_transcript(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the current transcript and processing status for a meeting."""
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    return TranscriptResponse(
        meeting_id=meeting.id,
        transcript=meeting.transcript,
        transcript_language=meeting.transcript_language,
        processing_status=meeting.processing_status,
        processing_started_at=meeting.processing_started_at,
        processing_completed_at=meeting.processing_completed_at,
        processing_error=meeting.processing_error,
    )


# ── Delete audio ──────────────────────────────────────────────────────────────

@router.delete("/{meeting_id}/audio", response_model=SuccessResponse)
def delete_audio(
    meeting_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete the audio file and reset transcription state for a meeting."""
    meeting = MeetingService.get_by_id(db, meeting_id, current_user.id)

    if not meeting.audio_file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No audio file found for this meeting.",
        )

    delete_audio_file(meeting.audio_file_path)

    # Reset all audio + transcript fields
    meeting.audio_file_path = None
    meeting.audio_file_size = None
    meeting.audio_original_name = None
    meeting.transcript = None
    meeting.transcript_language = None
    meeting.processing_status = "pending"
    meeting.processing_started_at = None
    meeting.processing_completed_at = None
    meeting.processing_error = None
    meeting.speaker_data = None
    db.commit()

    return SuccessResponse(message="Audio file and transcript deleted successfully.")
