"""
Audio file utility helpers for the speech module.
Handles file validation, unique naming, and storage paths.
"""
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)


def get_unique_audio_filename(original_filename: str) -> str:
    """
    Generate a collision-safe filename.
    Format: <uuid_hex>_<sanitized_original_name>
    """
    ext = Path(original_filename).suffix.lower()
    safe_stem = Path(original_filename).stem[:40].replace(" ", "_")
    return f"{uuid.uuid4().hex}_{safe_stem}{ext}"


def get_audio_storage_path(filename: str) -> Path:
    """Return the full absolute path for an audio file in uploads/audio/."""
    return settings.AUDIO_UPLOAD_DIR / filename


def get_audio_relative_path(filename: str) -> str:
    """Return the relative storage path (stored in DB)."""
    return f"uploads/audio/{filename}"


def validate_audio_file(file: UploadFile) -> None:
    """
    Validate audio file extension and size.
    Raises HTTPException on validation failure.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No file was provided.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"File type '{ext}' is not supported. "
                f"Allowed formats: {', '.join(settings.ALLOWED_AUDIO_EXTENSIONS)}"
            ),
        )


async def save_audio_file(file: UploadFile, filename: str) -> int:
    """
    Stream-write the uploaded file to disk.
    Returns the number of bytes written.
    Raises HTTPException if the file exceeds the size limit.
    """
    # Ensure the upload directory exists
    settings.AUDIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    destination = get_audio_storage_path(filename)
    total_bytes = 0
    chunk_size = 1024 * 1024  # 1 MB chunks

    try:
        with destination.open("wb") as out_file:
            while True:
                chunk = await file.read(chunk_size)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > settings.MAX_AUDIO_SIZE_BYTES:
                    out_file.close()
                    destination.unlink(missing_ok=True)  # clean up partial file
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=(
                            f"File too large. Maximum allowed size is "
                            f"{settings.MAX_UPLOAD_SIZE_MB} MB."
                        ),
                    )
                out_file.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        destination.unlink(missing_ok=True)
        logger.error("Failed to save audio file %s: %s", filename, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save audio file.",
        )

    logger.info("Saved audio file: %s (%d bytes)", filename, total_bytes)
    return total_bytes


def delete_audio_file(relative_path: str) -> bool:
    """
    Delete an audio file by its relative DB path.
    Returns True if deleted, False if not found.
    """
    full_path = settings.BASE_DIR / relative_path
    if full_path.exists():
        full_path.unlink()
        logger.info("Deleted audio file: %s", relative_path)
        return True
    return False
