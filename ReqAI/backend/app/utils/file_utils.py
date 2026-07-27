"""
File utility helpers used across the application.
Phase 2 will extend this for audio upload handling.
"""
import os
import uuid
from pathlib import Path

from app.core.config import settings


ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".flac", ".webm"}


def generate_unique_filename(original_filename: str) -> str:
    """Return a UUID-prefixed filename to prevent collisions."""
    ext = Path(original_filename).suffix.lower()
    return f"{uuid.uuid4().hex}{ext}"


def is_allowed_audio_file(filename: str) -> bool:
    """Check if the file extension is an accepted audio format."""
    ext = Path(filename).suffix.lower()
    return ext in ALLOWED_AUDIO_EXTENSIONS


def ensure_directories_exist() -> None:
    """Create required runtime directories if they don't exist."""
    for directory in [settings.UPLOAD_DIR, settings.GENERATED_DIR, settings.LOGS_DIR]:
        Path(directory).mkdir(parents=True, exist_ok=True)


def get_upload_path(filename: str) -> Path:
    """Return the full path for an uploaded audio file."""
    return settings.UPLOAD_DIR / filename


def get_generated_path(filename: str) -> Path:
    """Return the full path for a generated document file."""
    return settings.GENERATED_DIR / filename


def delete_file_if_exists(file_path: str) -> bool:
    """Delete a file and return True if it existed."""
    path = Path(file_path)
    if path.exists():
        path.unlink()
        return True
    return False
