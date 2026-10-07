"""
Application configuration.
All settings are loaded from environment variables with safe defaults.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from the backend root
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


class Settings:
    # ── Application ──────────────────────────────────────────────
    APP_NAME: str = os.getenv("APP_NAME", "ReqAI")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    APP_DESCRIPTION: str = os.getenv(
        "APP_DESCRIPTION",
        "AI Powered Business Requirement Document Generator",
    )
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    API_V1_PREFIX: str = "/api/v1"

    # ── Security ─────────────────────────────────────────────────
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "change-this-secret-key-in-production-please"
    )
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )

    # ── Database ──────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "sqlite:///./reqai.db"
    )

    # ── CORS ─────────────────────────────────────────────────────
    ALLOWED_ORIGINS: list = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5500,http://127.0.0.1:5500",
    ).split(",")

    # ── File Storage ─────────────────────────────────────────────
    BASE_DIR: Path = Path(__file__).resolve().parents[2]
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    GENERATED_DIR: Path = BASE_DIR / "generated"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Max audio upload size: 100 MB
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))

    # ── Audio Upload ──────────────────────────────────────────────
    AUDIO_UPLOAD_DIR: Path = BASE_DIR / "uploads" / "audio"
    ALLOWED_AUDIO_EXTENSIONS: set = {".mp3", ".wav", ".m4a", ".webm", ".ogg", ".flac"}
    MAX_AUDIO_SIZE_BYTES: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100")) * 1024 * 1024

    # ── Whisper (faster-whisper) ──────────────────────────────────
    # Model size options: tiny | base | small | medium | large-v2 | large-v3
    # Use "base" for development (fast), "medium" or "large-v2" for production accuracy
    WHISPER_MODEL_SIZE: str = os.getenv("WHISPER_MODEL_SIZE", "base")
    WHISPER_DEVICE: str = os.getenv("WHISPER_DEVICE", "cpu")   # cpu | cuda
    WHISPER_COMPUTE_TYPE: str = os.getenv("WHISPER_COMPUTE_TYPE", "int8")  # int8 | float16
    WHISPER_LANGUAGE: str = os.getenv("WHISPER_LANGUAGE", "en")  # None = auto-detect

    # ── pyannote.audio (Speaker Diarization – Phase 3) ────────────
    # HuggingFace token required to download pyannote models
    # Get your token at: https://huggingface.co/settings/tokens
    # Accept model terms at: https://huggingface.co/pyannote/speaker-diarization-3.1
    PYANNOTE_HF_TOKEN: str = os.getenv("PYANNOTE_HF_TOKEN", "")
    PYANNOTE_MODEL: str = os.getenv(
        "PYANNOTE_MODEL", "pyannote/speaker-diarization-3.1"
    )
    # Hint the expected number of speakers (None = auto-detect)
    PYANNOTE_NUM_SPEAKERS: int = int(os.getenv("PYANNOTE_NUM_SPEAKERS", "0"))
    # Maximum speakers to detect when count is unknown
    PYANNOTE_MAX_SPEAKERS: int = int(os.getenv("PYANNOTE_MAX_SPEAKERS", "10"))

    # ── spaCy NLP (Phase 4) ───────────────────────────────────────
    # Model: en_core_web_sm (fast) | en_core_web_md | en_core_web_lg
    SPACY_MODEL: str = os.getenv("SPACY_MODEL", "en_core_web_sm")

    # ── Sentence Transformers (Phase 6) ──────────────────────────
    # Model: all-MiniLM-L6-v2 — fast, 384-dim, strong semantic quality
    # See: https://www.sbert.net/docs/sentence_transformer/pretrained_models.html
    SIMILARITY_MODEL: str = os.getenv("SIMILARITY_MODEL", "all-MiniLM-L6-v2")

    # Duplicate threshold — pairs at or above this are POTENTIAL_DUPLICATE.
    # Default 0.85 is an initial calibration value.
    # Adjust based on your real project requirement corpus.
    # Lower (e.g. 0.80) catches more duplicates; higher (e.g. 0.90) is stricter.
    SIMILARITY_DUPLICATE_THRESHOLD: float = float(
        os.getenv("SIMILARITY_DUPLICATE_THRESHOLD", "0.85")
    )

    # Review threshold — pairs at or above this (but below duplicate_threshold)
    # are flagged as SIMILAR and surfaced for manual review.
    SIMILARITY_REVIEW_THRESHOLD: float = float(
        os.getenv("SIMILARITY_REVIEW_THRESHOLD", "0.65")
    )

    # ── Logging ───────────────────────────────────────────────────
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = str(LOGS_DIR / "reqai.log")

    # ── Groq LLM (Phase 7) ───────────────────────────────────────
    # NEVER hardcode the API key. Load from environment only.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.3"))
    GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "4096"))
    GROQ_TIMEOUT: int = int(os.getenv("GROQ_TIMEOUT", "60"))
    GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "3"))

    # BRD output directory
    BRD_DIR: Path = BASE_DIR / "generated" / "brd"


# Singleton instance used across the application
settings = Settings()
