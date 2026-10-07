"""
SpeechService – faster-whisper transcription service.

Responsibilities:
  - Load and cache the Whisper model (singleton pattern)
  - Transcribe an audio file to plain text
  - Save the transcript to the database

This service is completely isolated from the router layer.
Phase 3 will add diarization results alongside the transcript.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SpeechService:
    """
    Singleton-style service that holds one loaded Whisper model instance.
    The model is loaded lazily on first transcription request to avoid
    consuming memory when the speech module is not used.
    """

    _model = None               # cached WhisperModel instance
    _model_lock = threading.Lock()  # thread-safe lazy initialisation

    # ── Model management ──────────────────────────────────────────────────────

    @classmethod
    def load_model(cls):
        """
        Load (or return cached) faster-whisper WhisperModel.
        Thread-safe: only one thread initialises the model.

        Returns:
            WhisperModel instance.

        Raises:
            HTTPException 503 if faster-whisper is not installed.
            HTTPException 500 on any other loading failure.
        """
        if cls._model is not None:
            return cls._model

        with cls._model_lock:
            # Double-checked locking
            if cls._model is not None:
                return cls._model

            try:
                from faster_whisper import WhisperModel  # type: ignore
            except ImportError:
                logger.error("faster-whisper is not installed.")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Speech recognition model is not available. "
                        "Please install faster-whisper: pip install faster-whisper"
                    ),
                )

            try:
                logger.info(
                    "Loading Whisper model '%s' on device='%s' compute_type='%s' ...",
                    settings.WHISPER_MODEL_SIZE,
                    settings.WHISPER_DEVICE,
                    settings.WHISPER_COMPUTE_TYPE,
                )
                cls._model = WhisperModel(
                    settings.WHISPER_MODEL_SIZE,
                    device=settings.WHISPER_DEVICE,
                    compute_type=settings.WHISPER_COMPUTE_TYPE,
                )
                logger.info("Whisper model loaded successfully.")
            except Exception as exc:
                logger.error("Failed to load Whisper model: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to load speech recognition model: {str(exc)}",
                )

        return cls._model

    @classmethod
    def unload_model(cls) -> None:
        """Release the model from memory (useful for testing / hot-reload)."""
        with cls._model_lock:
            cls._model = None
        logger.info("Whisper model unloaded.")

    # ── Transcription ─────────────────────────────────────────────────────────

    @classmethod
    def transcribe_audio(cls, audio_path: Path) -> dict:
        """
        Transcribe an audio file using faster-whisper.

        Args:
            audio_path: Absolute path to the audio file.

        Returns:
            dict with keys:
                - text (str): Full transcript text
                - language (str): Detected or configured language code
                - segments (list): Raw segment dicts (reserved for Phase 3 speaker data)

        Raises:
            HTTPException 404 if audio file doesn't exist.
            HTTPException 422 if transcription produces no output.
            HTTPException 500 on unexpected error.
        """
        if not audio_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {audio_path.name}",
            )

        model = cls.load_model()

        # Determine language setting (None = auto-detect)
        language = settings.WHISPER_LANGUAGE if settings.WHISPER_LANGUAGE else None

        logger.info("Starting transcription: %s (language=%s)", audio_path.name, language or "auto")

        try:
            segments, info = model.transcribe(
                str(audio_path),
                language=language,
                beam_size=5,
                vad_filter=True,        # skip silent sections
                vad_parameters={"min_silence_duration_ms": 500},
            )

            # Materialise the lazy generator into a list
            segment_list = []
            full_text_parts = []
            for seg in segments:
                segment_list.append({
                    "start": round(seg.start, 2),
                    "end": round(seg.end, 2),
                    "text": seg.text.strip(),
                })
                full_text_parts.append(seg.text.strip())

            full_text = " ".join(full_text_parts).strip()

            if not full_text:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Transcription produced no text. The audio may be silent or corrupted.",
                )

            detected_language = info.language if info.language else (language or "unknown")
            logger.info(
                "Transcription complete: %d segments, language=%s, chars=%d",
                len(segment_list),
                detected_language,
                len(full_text),
            )

            return {
                "text": full_text,
                "language": detected_language,
                "segments": segment_list,  # kept for Phase 3 diarization mapping
            }

        except HTTPException:
            raise
        except Exception as exc:
            logger.error("Transcription failed for %s: %s", audio_path.name, exc, exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Transcription failed: {str(exc)}",
            )

    # ── Database persistence ──────────────────────────────────────────────────

    @classmethod
    def save_transcript(
        cls,
        db: Session,
        meeting,  # Meeting ORM instance
        transcript_result: dict,
    ) -> None:
        """
        Persist transcription results to the database.

        Args:
            db: Active SQLAlchemy session.
            meeting: Meeting ORM object to update.
            transcript_result: Dict returned by transcribe_audio().
        """
        import json

        meeting.transcript = transcript_result["text"]
        meeting.transcript_language = transcript_result["language"]
        meeting.processing_status = "completed"
        meeting.processing_completed_at = datetime.now(timezone.utc)
        meeting.processing_error = None

        # Store raw segments as JSON — Phase 3 will use these for speaker mapping
        if transcript_result.get("segments"):
            meeting.speaker_data = json.dumps(transcript_result["segments"])

        db.commit()
        db.refresh(meeting)
        logger.info("Transcript saved for meeting id=%d", meeting.id)

    @classmethod
    def mark_failed(cls, db: Session, meeting, error_message: str) -> None:
        """
        Update meeting status to 'failed' with an error message.
        """
        meeting.processing_status = "failed"
        meeting.processing_error = error_message
        meeting.processing_completed_at = datetime.now(timezone.utc)
        db.commit()
        logger.error("Transcription marked as failed for meeting id=%d: %s", meeting.id, error_message)
