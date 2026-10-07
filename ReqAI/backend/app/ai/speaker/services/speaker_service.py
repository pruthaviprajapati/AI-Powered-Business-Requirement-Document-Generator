"""
SpeakerService – pyannote.audio speaker diarization service.

Responsibilities:
  - Load and cache the pyannote diarization pipeline (singleton)
  - Run diarization on an audio file
  - Merge speaker turns with Whisper segments
  - Build speaker-labelled transcript
  - Persist results to the database

This service is completely isolated from the router layer.
Phase 4 (spaCy NLP) will consume speaker_transcript from the DB.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.ai.speaker.utils.diarization_utils import (
    assign_speaker_labels,
    build_speaker_segments,
    compute_speaker_summary,
    format_speaker_transcript,
    merge_whisper_and_diarization,
)
from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class SpeakerService:
    """
    Singleton-style diarization service.
    The pyannote pipeline is loaded lazily on first diarize() call.
    """

    _pipeline = None                   # cached pyannote Pipeline instance
    _pipeline_lock = threading.Lock()  # thread-safe lazy init

    # ── Model management ──────────────────────────────────────────────────────

    @classmethod
    def load_pipeline(cls):
        """
        Load (or return cached) pyannote diarization pipeline.

        Raises:
            HTTPException 503 if pyannote is not installed.
            HTTPException 503 if PYANNOTE_HF_TOKEN is not configured.
            HTTPException 500 on any other loading failure.
        """
        if cls._pipeline is not None:
            return cls._pipeline

        with cls._pipeline_lock:
            if cls._pipeline is not None:
                return cls._pipeline

            # ── Check pyannote is installed ────────────────────────
            try:
                from pyannote.audio import Pipeline  # type: ignore
            except ImportError:
                logger.error("pyannote.audio is not installed.")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "Speaker diarization model is not available. "
                        "Install it: pip install pyannote.audio"
                    ),
                )

            # ── Check HuggingFace token ────────────────────────────
            hf_token = settings.PYANNOTE_HF_TOKEN
            if not hf_token or hf_token == "your_huggingface_token_here":
                logger.error("PYANNOTE_HF_TOKEN is not set.")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=(
                        "HuggingFace token not configured. "
                        "Set PYANNOTE_HF_TOKEN in your .env file. "
                        "Get your token at https://huggingface.co/settings/tokens "
                        "and accept the model terms at "
                        "https://huggingface.co/pyannote/speaker-diarization-3.1"
                    ),
                )

            # ── Load pipeline ──────────────────────────────────────
            try:
                logger.info(
                    "Loading pyannote pipeline '%s' ...", settings.PYANNOTE_MODEL
                )
                cls._pipeline = Pipeline.from_pretrained(
                    settings.PYANNOTE_MODEL,
                    use_auth_token=hf_token,
                )
                logger.info("pyannote pipeline loaded successfully.")
            except Exception as exc:
                logger.error("Failed to load pyannote pipeline: %s", exc)
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to load speaker diarization model: {str(exc)}",
                )

        return cls._pipeline

    @classmethod
    def unload_pipeline(cls) -> None:
        """Release the pipeline from memory."""
        with cls._pipeline_lock:
            cls._pipeline = None
        logger.info("pyannote pipeline unloaded.")

    # ── Diarization ───────────────────────────────────────────────────────────

    @classmethod
    def diarize(cls, audio_path: Path) -> list[dict]:
        """
        Run pyannote diarization on an audio file.

        Returns:
            List of diarization turns:
            [{start: float, end: float, speaker: str}, ...]

        Raises:
            HTTPException 404 if audio file doesn't exist.
            HTTPException 422 if no speech detected.
            HTTPException 500 on unexpected error.
        """
        if not audio_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Audio file not found: {audio_path.name}",
            )

        pipeline = cls.load_pipeline()

        # Determine speaker count hints
        num_speakers = settings.PYANNOTE_NUM_SPEAKERS or None
        max_speakers = settings.PYANNOTE_MAX_SPEAKERS or None

        logger.info(
            "Starting diarization: %s (num_speakers=%s, max_speakers=%s)",
            audio_path.name,
            num_speakers,
            max_speakers,
        )

        try:
            # Build kwargs only with set values to avoid pyannote errors
            kwargs: dict = {}
            if num_speakers:
                kwargs["num_speakers"] = num_speakers
            elif max_speakers:
                kwargs["max_speakers"] = max_speakers

            diarization = pipeline(str(audio_path), **kwargs)

            # Convert pyannote Annotation into plain dicts
            turns = []
            for turn, _, speaker in diarization.itertracks(yield_label=True):
                turns.append({
                    "start": round(turn.start, 3),
                    "end": round(turn.end, 3),
                    "speaker": speaker,  # e.g. "SPEAKER_00"
                })

            if not turns:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        "No speakers detected in the audio. "
                        "The audio may be silent, too short, or contain no speech."
                    ),
                )

            unique_speakers = {t["speaker"] for t in turns}
            logger.info(
                "Diarization complete: %d turns, %d unique speakers",
                len(turns),
                len(unique_speakers),
            )
            return turns

        except HTTPException:
            raise
        except Exception as exc:
            logger.error(
                "Diarization failed for %s: %s", audio_path.name, exc, exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Speaker diarization failed: {str(exc)}",
            )

    # ── Full processing pipeline ──────────────────────────────────────────────

    @classmethod
    def process(cls, audio_path: Path, whisper_segments: list[dict]) -> dict:
        """
        Run full speaker diarization and merge with Whisper segments.

        Args:
            audio_path: Path to the audio file.
            whisper_segments: Segments list from SpeechService.transcribe_audio().

        Returns:
            dict with keys:
                - turns (list): raw pyannote turns
                - speaker_segments (list): merged, labelled, grouped segments
                - speaker_transcript (str): formatted transcript text
                - speaker_count (int): number of unique speakers
                - label_map (dict): raw_id → label mapping
        """
        # Step 1: run diarization
        turns = cls.diarize(audio_path)

        # Step 2: build label map from first-appearance order
        raw_speakers_ordered = []
        seen = set()
        for t in turns:
            if t["speaker"] not in seen:
                raw_speakers_ordered.append(t["speaker"])
                seen.add(t["speaker"])

        label_map = assign_speaker_labels(raw_speakers_ordered)

        # Step 3: merge Whisper segments with diarization turns
        merged = merge_whisper_and_diarization(whisper_segments, turns)

        # Step 4: group consecutive same-speaker turns, build final segments
        speaker_segments = build_speaker_segments(merged, label_map)

        # Step 5: format readable transcript
        speaker_transcript = format_speaker_transcript(speaker_segments)

        return {
            "turns": turns,
            "speaker_segments": speaker_segments,
            "speaker_transcript": speaker_transcript,
            "speaker_count": len(label_map),
            "label_map": label_map,
        }

    # ── Database persistence ──────────────────────────────────────────────────

    @classmethod
    def save_diarization(
        cls,
        db: Session,
        meeting,
        result: dict,
    ) -> None:
        """
        Persist diarization results to the database.

        Stores:
          - speaker_data: JSON of raw diarization turns
          - speaker_transcript: formatted labelled transcript
          - speaker_count: number of unique speakers
          - diarization_status: 'completed'
        """
        meeting.speaker_data = json.dumps(result["turns"])
        meeting.speaker_transcript = result["speaker_transcript"]
        meeting.speaker_count = result["speaker_count"]
        meeting.diarization_status = "completed"
        db.commit()
        db.refresh(meeting)
        logger.info(
            "Diarization saved for meeting id=%d (%d speakers)",
            meeting.id,
            result["speaker_count"],
        )

    @classmethod
    def mark_failed(cls, db: Session, meeting, error_message: str) -> None:
        """Mark diarization as failed with an error message."""
        meeting.diarization_status = "failed"
        # Store error in processing_error (shared field) so frontend can read it
        meeting.processing_error = error_message
        db.commit()
        logger.error(
            "Diarization marked as failed for meeting id=%d: %s",
            meeting.id,
            error_message,
        )

    @classmethod
    def mark_skipped(cls, db: Session, meeting, reason: str) -> None:
        """
        Mark diarization as skipped (e.g. single-speaker meeting).
        Builds a plain Speaker 1 transcript from the raw transcript.
        """
        meeting.diarization_status = "skipped"
        meeting.speaker_count = 1
        # Create a simple single-speaker transcript from raw transcript
        if meeting.transcript:
            meeting.speaker_transcript = f"[00:00 - --:--]\nSpeaker 1:\n{meeting.transcript}"
        db.commit()
        logger.info(
            "Diarization skipped for meeting id=%d: %s", meeting.id, reason
        )
